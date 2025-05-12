import time
from datetime import datetime
from typing import Any

from requests import Session

from common.constant import Constant
from common.exception import BusinessException
from common.utils import Utils
from service.login import Login


class SignIn:
    def __init__(self, module_parameter: dict[str, Any]) -> None:
        # 模块参数
        self.module_parameter = module_parameter
        # 会话对象
        self.session: Session = self.module_parameter.get("requests_session")
        # 获取logger
        self.logger = self.module_parameter.get("logger")
        # 获取用户配置
        self.user: dict[str, Any] = self.module_parameter.get("user")
        # 获取用户登陆信息
        self.user_login_info: dict[str, Any] = self.module_parameter.get("user_login_info")
        # 异常类
        self.exception = BusinessException("自动签到失败, 请前往app手动签到")
        # 创建请求参数字典
        self.request_parameter_dict = {
            "request_class_config": {
                "logger": self.logger,
                "session": self.session,
                "business_exception": self.exception
            },
            "method": "post"
        }

    def sign_in(self) -> None:

        self.logger.info(f"签到")

        # 上下班判断
        current_time = datetime.now()
        sing_in_type = "START" if current_time.hour < 12 else "END"

        """
        签到请求
        """
        # 地址信息
        address_setting: dict[str, Any] = self.user.get("configInfo").get("addressSetting")
        # 实习计划信息
        plan_info: dict[str, Any] = self.user_login_info.get("planInfo")
        # 登陆信息
        login_info: dict[str, Any] = self.user_login_info.get("loginInfo")
        # 构建请求体
        data: dict[str, str] = {
            "distance": None,
            "address": address_setting.get("address"),
            "content": None,
            "lastAddress": None,
            "lastDetailAddress": address_setting.get("address"),
            "attendanceId": None,
            "city": address_setting.get("city"),
            "area": address_setting.get("area"),
            "country": address_setting.get("country"),
            "createBy": None,
            "createTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": None,
            "device": "{brand: Xiaomi 24031PN0DC, systemVersion: 12, Platform: Android, isPhysicalDevice: true, incremental: 453}",
            "images": None,
            "isDeleted": None,
            "isReplace": None,
            "latitude": address_setting.get("latitude"),
            "longitude": address_setting.get("longitude"),
            "modifiedBy": None,
            "modifiedTime": None,
            "province": address_setting.get("province"),
            "schoolId": None,
            "state": "NORMAL",
            "teacherId": None,
            "teacherNumber": None,
            "type": sing_in_type,
            "stuId": None,
            "planId": plan_info.get("planId"),
            "attendanceType": None,
            "username": None,
            "attachments": None,
            "userId": login_info.get("userId"),
            "isSYN": None,
            "studentId": None,
            "applyState": None,
            "studentNumber": None,
            "memberNumber": None,
            "headImg": None,
            "attendenceTime": None,
            "depName": None,
            "majorName": None,
            "className": None,
            "logDtoList": None,
            "isBeyondFence": None,
            "practiceAddress": None,
            "tpJobId": None,
            "t": Utils.aes_encrypt(str(int(time.time() * 1000))).lower()
        }
        # 构造请求头
        self.session.headers.update({
            "Sign": Utils.md5_encrypt(
                data.get("device") + sing_in_type + plan_info.get("planId") + login_info.get(
                    "userId") + address_setting.get(
                    "address") + Constant.MD5_SALT)
        })
        # 请求参数构造
        self.request_parameter_dict.update({
            "url": Constant.BASE_URL + "/attendence/clock/v4/save",
            "data": data
        })

        # 获取请求结果
        res: dict = Utils.send_request(**self.request_parameter_dict)

        # 判断是否签到成功
        if res.get("code") == 401:
            # token失效
            self.logger.error(f"签到失败 > 失败原因: token失效 (即将重新获取token)")
            # 重新获取登陆信息
            Login(self.module_parameter).login()
            # 更新Sign以及data
            self.session.headers.update({
                "Sign": Utils.md5_encrypt(
                    data.get("device") + sing_in_type + plan_info.get("planId") + login_info.get(
                        "userId") + address_setting.get(
                        "address") + Constant.MD5_SALT)
            })
            data.update({
                "createTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "t": Utils.aes_encrypt(str(int(time.time() * 1000))).lower()
            })
            # 重新发送签到请求
            res: dict = Utils.send_request(**self.request_parameter_dict)

            # 仍未签到成功，则失败
            if res.get("code") != 200:
                self.logger.error(f"签到失败 > 失败原因: {res.get('msg')}")
                raise self.exception

        # 其他异常情况
        elif res.get("code") != 200:
            self.logger.error(f"签到失败 > 失败原因: {res.get('msg')}")
            raise self.exception

        self.logger.info(f"签到完成")


if __name__ == '__main__':
    pass
