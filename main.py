import datetime
import sys
import threading
import time
from pathlib import Path
from typing import Any

import requests
import schedule
from dotenv import load_dotenv
from loguru import logger as loguru_logger
from requests import Session

from common.constant import Constant
from common.exception import BusinessException
from common.logger_manager import LoggerManager
from common.utils import Utils
from service.login import Login
from service.monthly_report import MonthlyReport
from service.sign_in import SignIn
from service.weekly_report import WeeklyReport

USERS_LOGIN_INFO_PATH = (Path(__file__).parent / "data/users_login_info.json").resolve()
USERS_PATH = (Path(__file__).parent / "data/users.json").resolve()


class ScheduledTask:

    @staticmethod
    def task_for_user(user: dict[str, Any]) -> None:
        # 获取logger
        logger: loguru_logger = LoggerManager.get_user_logger(user.get("username"))
        # 创建会话对象
        requests_session: Session = requests.Session()
        # 伪装请求头
        requests_session.headers.update(Constant.HEADERS)
        # 模块参数
        module_parameter: dict[str, Any] = {
            "user": user,
            "user_login_info": {},
            "requests_session": requests_session,
            "logger": logger,
        }
        # 提醒邮箱
        email: str = user.get("email")

        # 自动化任务开始
        logger.info(f"自动化任务执行开始...")

        # 检查是否存在登陆信息，不存在则重新获取
        logger.info(f"获取登陆信息")
        # 读取用户登陆信息
        user_login_info: dict[str, Any] = Utils.operate_json_file(USERS_LOGIN_INFO_PATH).get(user.get("username"))

        if not user_login_info:
            logger.info(f"未获取到登陆信息, 调用登陆模块进行获取登陆信息")
            try:
                Login(module_parameter).login()
            except BusinessException:
                logger.error(f"获取登陆信息失败, 自动化任务结束")
                Utils.send_email(email, "在获取登陆信息时, 发生未知错误导致获取失败, 影响自动化任务: 签到 周报 月报",
                                 logger)
                return
        else:
            # 加载Authorization
            requests_session.headers.update({
                "Authorization": user_login_info.get("loginInfo").get("token"),
            })
            # 更新登陆信息
            module_parameter.update(user_login_info=user_login_info)
        logger.info(f"获取登陆信息完成")

        # 获取用户任务时间设置
        time_setting = user.get("configInfo").get("timeSetting")

        now = datetime.datetime.now()

        # 签到时间
        sign_in_time = time_setting.get('signInTime')
        # 周报时间
        weekly_report_time = time_setting.get('weeklyReportTime')
        # 月报时间
        monthly_report_time = time_setting.get('monthlyReportTime')

        # 签到
        try:
            if sign_in_time and (sign_in_time.get("start") == now.hour or sign_in_time.get("end") == now.hour):
                SignIn(module_parameter).sign_in()
            else:
                logger.info(f"签到任务不在用户指定时间")
        except BusinessException as e:
            logger.error(f"{e}")
            Utils.send_email(email, str(e), logger)

        # 提交周报
        try:
            if weekly_report_time and weekly_report_time.get("week") == (now.weekday() + 1) and weekly_report_time.get(
                    "time") == now.hour:
                WeeklyReport(module_parameter).submit_weekly_report()
            else:
                logger.info(f"周报任务不在用户指定时间")
        except BusinessException as e:
            logger.error(f"{e}")
            Utils.send_email(email, str(e), logger)

        # 提交月报
        try:
            if monthly_report_time and monthly_report_time.get("day") == now.day and monthly_report_time.get(
                    "time") == now.hour:
                MonthlyReport(module_parameter).sub_monthly_report()
            else:
                logger.info(f"月报任务不在用户指定时间")
        except BusinessException as e:
            logger.error(f"{e}")
            Utils.send_email(email, str(e), logger)

        # 资源释放
        requests_session.close()

        logger.info(f"自动化任务执行结束...")

    @staticmethod
    def task() -> None:
        threads: list[threading.Thread] = []

        # 读取 users 文件
        users: list[dict[str, Any]] = Utils.operate_json_file(USERS_PATH).get("users")

        if not users:
            return

        for user in users:
            # 创建一个线程来执行每个用户的任务
            thread = threading.Thread(target=ScheduledTask.task_for_user, args=(user,))
            threads.append(thread)
            thread.start()

        # 等待所有线程执行完成
        for thread in threads:
            thread.join()

    @staticmethod
    def start() -> None:
        # 设置任务，在每小时的整点执行
        schedule.every().hour.at(":00").do(ScheduledTask.task)
        # 保持脚本运行，等待并执行定时任务
        while True:
            schedule.run_pending()  # 检查是否有任务需要执行
            time.sleep(1)  # 每秒检查一次


class ExecutedSeparately:
    @staticmethod
    def start() -> None:
        print("获取用户信息中...")
        # 读取 users 文件
        users: list[dict[str, Any]] = Utils.operate_json_file(USERS_PATH).get("users")

        # 检查用户列表是否为空
        if not users:
            # 如果没有获取到用户信息，提示用户添加信息并退出程序
            input("没有获取到用户信息, 请在users.json中添加用户信息后重试")
            sys.exit(0)

        # 打印获取到的用户数量和信息
        print(f"获取到{len(users)}名用户信息, 如下↓")
        # 遍历用户列表，显示每个用户的序号和用户名
        for index, user in enumerate(users):
            print(f"序号: {index}, 名称: {user.get('username')}")

        # 进入用户选择循环
        while True:
            # 提示用户输入要选择的用户序号
            user_index = input("请输入要执行任务的用户序号: ")
            try:
                # 尝试将输入转换为整数
                user_index = int(user_index)
                # 检查序号是否在有效范围内
                if not 0 <= user_index < len(users):
                    # 如果不在范围内，抛出异常
                    raise ValueError("用户序号无效")
                # 如果输入有效，跳出循环
                break
            except ValueError:
                # 捕获转换失败或范围无效的异常，提示用户重新输入
                print("请输入正确的用户序号")

        # 获取选择的用户信息
        user = users[user_index]
        # 创建会话对象
        requests_session: Session = requests.Session()
        # 伪装请求头
        requests_session.headers.update(Constant.HEADERS)
        # 获取logger
        logger: loguru_logger = LoggerManager.get_user_logger(user.get("username"))

        # 模块参数
        module_parameter: dict[str, Any] = {
            "user": user,
            "user_login_info": {},
            "requests_session": requests_session,
            "logger": logger,
        }
        # 检查是否存在登陆信息，不存在则重新获取
        # 读取用户登陆信息
        user_login_info: dict[str, Any] = Utils.operate_json_file(USERS_LOGIN_INFO_PATH).get(user.get("username"))

        if not user_login_info:
            try:
                Login(module_parameter).login()
            except BusinessException:
                input("获取登陆信息失败, 请在用户日志中查看详情")
                sys.exit(0)
        else:
            # 加载Authorization
            requests_session.headers.update({
                "Authorization": user_login_info.get("loginInfo").get("token"),
            })
            # 更新登陆信息
            module_parameter.update(user_login_info=user_login_info)

        # 任务选择
        while True:
            task_no = input("请选择要执行的任务序号( 1.签到 2.提交周报 3.提交月报 ): ")
            try:
                task_no = int(task_no)
                if task_no not in range(1, 4):
                    raise ValueError("无效的任务序号")
                break
            except ValueError:
                print("请输入正确的任务序号")

        # 执行任务
        if task_no == 1:
            # 签到
            try:
                print("正在处理签到任务, 请耐心等待")
                logger.info("手动执行签到任务")
                SignIn(module_parameter).sign_in()
                input()
            except BusinessException:
                input("签到任务失败, 请在用户日志中查看详情")
        elif task_no == 2:
            # 提交周报
            try:
                print("正在处理周报任务, 请耐心等待")
                logger.info("手动执行周报任务")
                WeeklyReport(module_parameter).submit_weekly_report()
                input()
            except BusinessException:
                input("提交周报任务失败, 请在用户日志中查看详情")
        elif task_no == 3:
            # 提交月报
            try:
                print("正在处理月报任务, 请耐心等待")
                logger.info("手动执行月报任务")
                MonthlyReport(module_parameter).sub_monthly_report()
                input()
            except BusinessException:
                input("提交月报任务失败, 请在用户日志中查看详情")


if __name__ == '__main__':
    # 加载 .env 文件
    load_dotenv()
    # 获取命令行参数列表
    args = sys.argv
    # 检测文件是否存在
    if not USERS_PATH.exists():
        input("用户配置文件不存在, 请根据users.example.json示例, 添加users.json用户配置文件")
        sys.exit(0)
    if not USERS_LOGIN_INFO_PATH.exists():
        Utils.operate_json_file(USERS_LOGIN_INFO_PATH, "w", {})

    # 检查是否有参数传入，并且第一个参数是否为 "--single"
    if len(args) > 1 and args[1] == "--single":
        # 如果满足条件，执行单独运行模式
        ExecutedSeparately.start()
    else:
        # 否则执行定时任务模式
        ScheduledTask.start()
