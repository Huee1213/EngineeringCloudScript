import time
from datetime import datetime
from typing import Any

from requests import Session

from common.constant import Constant
from common.exception import BusinessException
from common.utils import Utils
from service.login import Login


class MonthlyReport:
    def __init__(self, module_parameter: dict[str, Any]):
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
        self.exception = BusinessException("自动提交月报失败, 请前往app手动提交")
        # 创建请求参数字典
        self.request_parameter_dict = {
            "request_class_config": {
                "logger": self.logger,
                "session": self.session,
                "business_exception": self.exception
            },
            "method": "post"
        }

    def sub_monthly_report(self) -> None:
        self.logger.info(f"处理月报")

        # 登陆信息
        login_info: dict[str, Any] = self.user_login_info.get("loginInfo")
        # 实习计划信息
        plan_info: dict[str, Any] = self.user_login_info.get("planInfo")
        # 岗位信息
        job_setting: dict[str, Any] = self.user.get("configInfo").get("jobSetting")

        """
        获取提交月
        """
        # 转换为 datetime 对象
        start_date = datetime.strptime(plan_info.get("startTime"), '%Y-%m-%d %H:%M:%S')
        end_date = datetime.strptime(plan_info.get("endTime"), '%Y-%m-%d %H:%M:%S')

        # 用来存储结果的列表
        sub_month_list = []

        # 当前日期初始化为开始日期
        current_date = start_date.replace(day=1)  # 设置为当前月的第一天

        # 循环直到当前日期超过结束日期
        while current_date <= end_date:
            # 将当前日期按 "YYYY-MM" 格式添加到列表
            sub_month_list.append(current_date.strftime('%Y-%m'))
            # 按月递增
            next_month = current_date.month % 12 + 1
            year_increment = 1 if current_date.month == 12 else 0
            current_date = current_date.replace(year=current_date.year + year_increment, month=next_month)

        """
        获取最后一次月报提交时间
        """
        # 构建请求体
        data = {
            "t": Utils.aes_encrypt(str(int(time.time() * 1000))),
            "currPage": 1,
            "pageSize": 25,
            "planId": plan_info.get("planId"),
            "reportType": "month"
        }
        # 构建请求头
        self.session.headers.update({
            "Sign": Utils.md5_encrypt(
                login_info.get("userId") + login_info.get("roleKey") + "month" + Constant.MD5_SALT)
        })

        # 请求参数构造
        self.request_parameter_dict.update({
            "url": Constant.BASE_URL + "/practice/paper/v2/listByStu",
            "data": data
        })

        # 获取请求结果
        res: dict = Utils.send_request(**self.request_parameter_dict)

        # 判断是否获取成功
        if res.get("code") == 401:
            # token失效
            self.logger.error(f"获取提交月失败 > 失败原因: token失效 (即将重新获取token)")
            # 重新获取登陆信息
            Login(self.module_parameter).login()
            # 更新Sign以及data
            data.update({
                "t": Utils.aes_encrypt(str(int(time.time() * 1000)))
            })
            self.session.headers.update({
                "Sign": Utils.md5_encrypt(
                    login_info.get("userId") + login_info.get("roleKey") + "month" + Constant.MD5_SALT)
            })
            # 重新发送请求
            res: dict = Utils.send_request(**self.request_parameter_dict)

            # 仍未成功，则失败
            if res.get("code") != 200:
                self.logger.error(f"获取提交月失败 > 失败原因: {res.get('msg')}")
                raise self.exception

        # 其他异常情况
        elif res.get("code") != 200:
            self.logger.error(f"获取提交月失败 > 失败原因: {res.get('msg')}")
            raise self.exception

        # 月报数据
        month_report_data = res.get("data")

        # 最后一次提交月
        last_sub_week = month_report_data[0].get("yearmonth") if month_report_data else "2024-10"
        # 当前系统时间
        current_time = datetime.now()

        # 将最后一次提交时间转换为 datetime 对象（设置为该月的 1 号）
        last_submit_datetime = datetime.strptime(last_sub_week, "%Y-%m")

        # 获取在最后一次提交时间之后，且不超过当前系统时间的日期（不包含最后一次提交时间）
        need_sub_time_list = [
            _ for _ in sub_month_list
            if last_submit_datetime < datetime.strptime(_, "%Y-%m") < current_time
        ]

        # 需要提交月报的时间段为空，则不进行处理月报
        if not need_sub_time_list:
            self.logger.info(f"暂未需要处理的月报")
            return

        # 需要提交月报的时间段不为空，则进行月报提交
        for sub_time in need_sub_time_list:

            sub_time_split = sub_time.split("-")

            self.logger.info(f"提交{sub_time_split[0]}年{sub_time_split[1]}月月报")

            self.logger.info(f"生成{sub_time_split[0]}年{sub_time_split[1]}月月报内容")

            content = None

            for _ in range(1, 4):
                # 利用ai生成周报
                content = Utils.report_assistant(
                    f"撰写一份{job_setting.get('post')}{sub_time_split[0]}年{sub_time_split[1]}月月报，只要纯文本，语言简洁，不要太多的格式")
                if type(content) == str:
                    break

                self.logger.error(f"生成周报失败 > 失败原因: {content}")

                # 如果已达到最大重试次数, 停止生成
                if _ == 3:
                    self.logger.error(f"生成周报失败，超过最大重试次数！")
                    raise self.exception

            """
            提交月报
            """
            # 构建请求
            data = {
                "t": Utils.aes_encrypt(str(int(time.time() * 1000))),
                "imageList": [],
                "title": f"{sub_time_split[0]}年{sub_time_split[1]}月月报",
                "content": content,
                "planId": plan_info.get("planId"),
                "reportType": "month",
                "yearmonth": sub_time
            }

            # 请求参数构造
            self.request_parameter_dict.update({
                "url": Constant.BASE_URL + "/practice/paper/v6/save",
                "data": data
            })

            # 构建请求头
            self.session.headers.update({
                "Sign": Utils.md5_encrypt(
                    login_info.get("userId") + data["reportType"] + plan_info.get("planId") + data[
                        "title"] + Constant.MD5_SALT)
            })

            # 提交月报
            Utils.send_request(**self.request_parameter_dict)

            self.logger.info(f"提交{sub_time_split[0]}年{sub_time_split[1]}月月报成功")

            time.sleep(60)

        self.logger.info(f"月报处理完毕")


if __name__ == '__main__':
    pass
