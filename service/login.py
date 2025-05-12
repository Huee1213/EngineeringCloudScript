import json
import time
from pathlib import Path
from threading import Lock
from typing import Any

from loguru import logger as loguru_logger
from requests import Session

from common.constant import Constant
from common.exception import BusinessException
from common.utils import Utils

file_lock = Lock()


class Login:

    def __init__(self, module_parameter: dict[str, Any]) -> None:
        # 创建会话对象
        self.session: Session = module_parameter.get("requests_session")
        # 滑块验证数据
        self.slider_auth_data_str = None
        # 用户登陆信息
        self.user_login_info: dict[str, Any] = module_parameter.get("user_login_info")
        # 用户配置信息
        self.user: dict[str, Any] = module_parameter.get("user")
        #  获取logger
        self.logger: loguru_logger = module_parameter.get("logger")
        # UUID
        self.uuid = "slider-" + Utils.generate_uuid()
        # 异常类
        self.exception = BusinessException("获取用户登陆信息失败")
        # 创建请求参数字典
        self.request_parameter_dict = {
            "request_class_config": {
                "logger": self.logger,
                "session": self.session,
                "business_exception": self.exception
            },
            "method": "post"
        }

    def send_verify_request(self, data: dict[str, str], slider_auth_data_str: str, captcha_data: dict[str, Any]) -> \
            dict[str, Any] | None:
        """
        构建请求数据并发送请求，检查图形验证码的验证结果。

        :param data: 请求的基础数据
        :param slider_auth_data_str: 滑动验证数据（已加密）
        :param captcha_data: 验证码相关的数据
        :return: 验证结果数据，如果发生异常，返回None
        """
        # 更新请求数据
        self.slider_auth_data_str = slider_auth_data_str
        data.update({
            "pointJson": Utils.aes_encrypt_base64(slider_auth_data_str, captcha_data.get("data").get("secretKey"))
        })

        # 请求参数构造
        self.request_parameter_dict.update({
            "url": Constant.BASE_URL + "/session/captcha/v1/check",
            "data": data
        })

        # 获取请求结果
        res: dict = Utils.send_request(**self.request_parameter_dict)

        # 验证码通过返回响应数据
        if res.get("code") == 200:
            return res

        # 验证码失效
        elif res.get("code") == 6110:
            self.logger.error(f"验证验证码失败 > 失败原因: {res.get('msg')}")
            return None

        # 默认返回None表示失败
        return None

    def get_captcha(self) -> dict[str, Any] | None:
        # 构建请求体
        data: dict[str, str | int] = {
            "captchaType": "blockPuzzle",
            "ts": int(time.time() * 1000),
            "clientUid": self.uuid,
            "t": Utils.aes_encrypt(str(int(time.time() * 1000)))
        }

        # 请求参数构造
        self.request_parameter_dict.update({
            "url": Constant.BASE_URL + "/session/captcha/v1/get",
            "data": data,
        })

        # 获取请求结果
        res: dict = Utils.send_request(**self.request_parameter_dict)

        if res.get("code") == 200:
            return res

        return None

    def solve_captcha(self, captcha_data: dict[str, dict[str, Any]]) -> dict | None:
        """
        解决验证码，检查滑块与拼图的匹配。

        :param captcha_data: 包含验证码信息的数据
        :return: 验证码验证结果
        """
        # 构建请求体
        data: dict[str, str] = {
            "captchaType": "blockPuzzle",
            "token": captcha_data.get("data").get("token"),
            "t": Utils.aes_encrypt(str(int(time.time() * 1000)))
        }

        # 获取滑块图像信息
        slider_data: dict = Utils.picture_identify(
            Utils.decode_base64_image(captcha_data.get("data").get("jigsawImageBase64"))
        )

        # 获取拼图图像信息
        jigsaw_data: dict = Utils.picture_identify(
            Utils.decode_base64_image(captcha_data.get("data").get("originalImageBase64"))
        )

        # 判断数据是否为空
        if not slider_data or not jigsaw_data:
            return None

        # 滑块图形y值
        slider_data_y: int = list(slider_data.keys())[0]

        # 判断滑块值与拼图值是否相等，相等直接构建需要滑动的距离
        if slider_data_y in jigsaw_data.keys():
            # 获取需要滑动的距离
            need_slide_distance = Utils.generate_random_float(jigsaw_data.get(slider_data_y))
            # 构建请求数据
            slider_auth_data_str = '{{"x":{},"y":5}}'.format(need_slide_distance)
            # 发送请求并返回结果
            return self.send_verify_request(data, slider_auth_data_str, captcha_data)

        # 如果不相等，进行范围判断（正负3的范围）
        for jigsaw_slider_key in jigsaw_data.keys():
            if (slider_data_y - 3) < jigsaw_slider_key < (slider_data_y + 3):
                # 获取需要滑动的距离
                need_slide_distance = Utils.generate_random_float(jigsaw_data.get(jigsaw_slider_key))
                # 构建请求数据
                slider_auth_data_str = '{{"x":{},"y":5}}'.format(need_slide_distance)
                # 发送请求并返回结果
                return self.send_verify_request(data, slider_auth_data_str, captcha_data)

        # 如果验证不通过，返回None
        return None

    def login(self) -> None:
        self.logger.info(f"登陆")

        # 图形验证码处理
        auth_data = dict()
        captcha_data = dict()
        # 3次认证机会，超过失败
        self.logger.info(f"图形验证码处理")
        retries = 3
        for _ in range(1, retries + 1):
            # 获取图形验证码数据
            captcha_data: dict[str, Any] = self.get_captcha()

            # 未获取到图形验证码数据，跳过当前循环
            if not captcha_data:
                self.logger.error(f"获取图形验证码数据失败 (尝试 {_}/{retries})")
                time.sleep(60)
                continue

            # 自动认证图形验证码
            auth_data: dict[str, Any] = self.solve_captcha(captcha_data)

            # 认证通过，则跳出循环
            if auth_data:
                break

            self.logger.error(f"自动认证图形验证码失败 (尝试 {_}/{retries})")

        # 认证失败，抛出业务异常
        if not auth_data:
            raise self.exception

        """
        登陆请求
        """
        # 构建请求体
        data: dict[str, str] = {
            "phone": Utils.aes_encrypt(self.user.get("phone")),
            "password": Utils.aes_encrypt(self.user.get("password")),
            "loginType": "web",
            "uuid": self.uuid,
            "t": Utils.aes_encrypt(str(int(time.time() * 1000))),
            "captcha": Utils.aes_encrypt_base64(
                auth_data.get("data").get("token") + "---" + self.slider_auth_data_str,
                captcha_data.get("data").get("secretKey"))
        }

        # 请求参数构造
        self.request_parameter_dict.update({
            "url": Constant.BASE_URL + "/session/user/v6/login",
            "data": data
        })

        # 获取请求结果
        res: dict = Utils.send_request(**self.request_parameter_dict)

        # 检查返回的 JSON 是否表示成功
        if res.get("code") != 200:
            self.logger.error(f"登陆失败 > 失败原因: {res.get('msg')}")
            raise self.exception

        # 获取响应数据并解码获取token
        login_info = json.loads(Utils.aes_decrypt_hex(res.get("data")))
        self.user_login_info.update({
            "loginInfo": login_info
        })

        self.logger.info(f"登陆完成")

        # 获取实习计划
        self.logger.info(f"获取实习计划")

        """
        实习计划请求
        """
        # 更新请求头
        self.session.headers.update({
            "Authorization": login_info.get("token"),
            "Sign": Utils.md5_encrypt(
                login_info.get("userId") + login_info.get("roleKey") + Constant.MD5_SALT)
        })

        # 请求参数构造
        self.request_parameter_dict.update({
            "url": Constant.BASE_URL + "/practice/plan/v4/getPlanByStu",
            "data": {
                "t": Utils.aes_encrypt(str(int(time.time() * 1000)))
            }
        })

        # 获取请求结果
        res: dict = Utils.send_request(**self.request_parameter_dict)

        # 检查返回的 JSON 是否表示成功
        if res.get("code") != 200:
            self.logger.error(f"获取实习计划失败 > 失败原因: {res.get('msg')}")
            raise self.exception

        # 获取响应数据
        self.user_login_info.update({
            "planInfo": res.get("data")[0]
        })

        self.logger.info(f"获取实习计划完成")

        # 更新用户登陆信息
        file_path = (Path(__file__).parent.parent / "data/users_login_info.json").resolve()

        with file_lock:
            # 读取 users_login_info 文件
            users_login_info = Utils.operate_json_file(file_path)
            # 写入 users_login_info 文件
            users_login_info.update({
                self.user.get("username"): self.user_login_info
            })
            Utils.operate_json_file(file_path, "w", users_login_info)

        self.logger.info(f"登陆流程完毕")


if __name__ == '__main__':
    pass
