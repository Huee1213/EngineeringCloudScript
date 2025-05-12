import time
from datetime import datetime
from typing import Any

from requests import Session

from common.constant import Constant
from common.exception import BusinessException
from common.utils import Utils
from service.login import Login


class WeeklyReport:
    def __init__(self, module_parameter: dict[str, Any]) -> None:
        # 模块参数
        self.module_parameter = module_parameter
        # 会话对象
        self.session: Session = self.module_parameter.get("requests_session")
        # 获取用户配置
        self.user: dict[str, Any] = self.module_parameter.get("user")
        # 获取用户登陆信息
        self.user_login_info: dict[str, Any] = self.module_parameter.get("user_login_info")
        # 获取logger
        self.logger = self.module_parameter.get("logger")
        # 异常类
        self.exception = BusinessException("自动提交周报失败, 请前往app手动提交")
        # 创建请求参数字典
        self.request_parameter_dict = {
            "request_class_config": {
                "logger": self.logger,
                "session": self.session,
                "business_exception": self.exception
            },
            "method": "post"
        }

    def submit_weekly_report(self) -> None:
        self.logger.info(f"处理周报")

        # 实习计划信息
        plan_info: dict[str, Any] = self.user_login_info.get("planInfo")
        # 登陆信息
        login_info: dict[str, Any] = self.user_login_info.get("loginInfo")
        # 岗位信息
        job_setting: dict[str, Any] = self.user.get("configInfo").get("jobSetting")

        """
        获取提交周
        """
        # 构建请求体
        data = {
            "t": Utils.aes_encrypt(str(int(time.time() * 1000))),
            "planId": plan_info.get("planId")
        }

        # 请求参数构造
        self.request_parameter_dict.update({
            "url": Constant.BASE_URL + "/practice/paper/v3/getWeeks1",
            "data": data
        })

        # 获取请求结果
        res: dict = Utils.send_request(**self.request_parameter_dict)

        # 判断是否获取成功
        if res.get("code") == 401:
            # token失效
            self.logger.error(f"获取提交周失败 > 失败原因: token失效 (即将重新获取token)")
            # 重新获取登陆信息
            Login(self.module_parameter).login()
            # 更新data
            data.update({
                "t": Utils.aes_encrypt(str(int(time.time() * 1000)))
            })
            # 重新发送请求
            res: dict = Utils.send_request(**self.request_parameter_dict)

            # 仍未成功，则失败
            if res.get("code") != 200:
                self.logger.error(f"获取提交周失败 > 失败原因: {res.get('msg')}")
                raise self.exception

        # 其他异常情况
        elif res.get("code") != 200:
            self.logger.error(f"获取提交周失败 > 失败原因: {res.get('msg')}")
            raise self.exception

        # 提交时间列表
        sub_time_list = list()

        for _ in res.get("data"):
            sub_time_list.append([
                _.get("endTime"),
                _.get("startTime")
            ])

        """
        获取最后一次周报提交时间
        """
        # 构建请求头
        self.session.headers.update({
            "Sign": Utils.md5_encrypt(
                login_info.get("userId") + login_info.get("roleKey") + "week" + Constant.MD5_SALT)
        })

        # 请求参数构造
        self.request_parameter_dict.update({
            "url": Constant.BASE_URL + "/practice/paper/v2/listByStu",
            "data": {
                "t": Utils.aes_encrypt(str(int(time.time() * 1000))),
                "currPage": 1,
                "pageSize": 25,
                "planId": plan_info.get("planId"),
                "reportType": "week"
            }
        })

        # 获取请求结果
        res: dict = Utils.send_request(**self.request_parameter_dict)

        # 周报数据
        weekly_report_data = res.get("data")
        last_sub_week = 0
        need_sub_time_list = sub_time_list

        if weekly_report_data:
            # 最后一次提交周
            last_sub_week = int(weekly_report_data[0].get("weeks").replace("第", "").replace("周", ""))
            # 将最后一次提交的时间转换为 datetime 对象
            last_sub_time = datetime.strptime(weekly_report_data[0].get("endTime"), '%Y-%m-%d %H:%M:%S')
            # 用于存储符合条件的时间段
            need_sub_time_list = []
            # 遍历时间列表
            for time_period in sub_time_list:
                # 将开始时间和结束时间转换为 datetime 对象
                start_time = datetime.strptime(time_period[1], '%Y-%m-%d %H:%M:%S')

                # 如果开始时间在最后一次提交时间之后，并且结束时间在开始时间之后
                if start_time > last_sub_time:
                    need_sub_time_list.append(time_period)

        # 需要提交周报的时间段为空，则不进行处理周报
        if not need_sub_time_list:
            self.logger.info(f"暂未需要处理的周报")
            return

        # 需要提交周报的时间段不为空，则进行周报提交
        for sub_time in reversed(need_sub_time_list):
            # 提交周
            last_sub_week = last_sub_week + 1

            self.logger.info(f"提交第{last_sub_week}周周报")

            self.logger.info(f"生成第{last_sub_week}周周报内容")

            content = None

            for _ in range(1, 4):
                # 利用ai生成周报
                content = Utils.report_assistant(
                    f"撰写一份{job_setting.get('post')}第{last_sub_week}周周报，只要纯文本，语言简洁，不要太多的格式，以及不要出现具体的时间日期")
                if type(content) == str:
                    break

                self.logger.error(f"生成周报失败 > 失败原因: {content}")

                # 如果已达到最大重试次数, 停止生成
                if _ == 3:
                    self.logger.error(f"生成周报失败，超过最大重试次数！")
                    raise self.exception
            """
            提交周报
            """
            # 构建请求体
            data = {
                "t": Utils.aes_encrypt(str(int(time.time() * 1000))),
                "imageList": [],
                "title": f"第{last_sub_week}周周记",
                "content": content,
                "planId": plan_info.get("planId"),
                "reportType": "week",
                "weeks": f"第{last_sub_week}周",
                "startTime": sub_time[1],
                "endTime": sub_time[0]
            }
            # 构建请求头
            self.session.headers.update({
                "Sign": Utils.md5_encrypt(
                    login_info.get("userId") + data["reportType"] + plan_info.get("planId") + data[
                        "title"] + Constant.MD5_SALT)
            })
            # 请求参数构造
            self.request_parameter_dict.update({
                "url": Constant.BASE_URL + "/practice/paper/v6/save",
                "data": data
            })

            # 提交周报
            Utils.send_request(**self.request_parameter_dict)

            self.logger.info(f"提交第{last_sub_week}周周报成功")

            time.sleep(60)

        self.logger.info(f"周报处理完毕")


if __name__ == '__main__':
    pass
