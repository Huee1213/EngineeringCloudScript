import base64
import binascii
import hashlib
import json
import os
import random
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from openai import OpenAI, OpenAIError
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam
from requests import RequestException, Response

from common.constant import Constant


class Utils:
    @staticmethod
    def operate_json_file(path: str | Path, mode: str = "r", data: dict[str, Any] = None) -> dict[str, Any] | None:
        if mode == "r":
            with open(file=path, encoding="utf-8") as file:
                return json.load(file)
        elif mode == "w" and type(data) is dict:
            with open(file=path, mode="w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
        else:
            raise ValueError("参数不合法")

        return None

    @staticmethod
    def aes_encrypt(input_string, key: str | bytes = Constant.AES_ENCRYPT_SECRET_KEY):
        """
        AES 加密函数，将输入字符串加密为密文，使用 ECB 模式和 Pkcs7 填充。

        :param input_string: 需要加密的字符串
        :param key: 用于加密的密钥（必须为 16、24 或 32 字节）
        :return: 加密后的密文（十六进制表示）
        """

        # 将输入字符串转换为字节
        data = input_string.encode('utf-8')

        # 将输入密钥转换为字节
        if type(key) != bytes:
            key = key.encode('utf8')

        # 填充数据
        cipher = AES.new(key, AES.MODE_ECB)

        # 使用 Pkcs7 填充
        padded_data = pad(data, AES.block_size)

        # 执行加密
        encrypted_data = cipher.encrypt(padded_data)

        # 返回密文，转为大写的十六进制字符串
        return binascii.hexlify(encrypted_data).decode('utf-8').upper()

    @staticmethod
    def aes_encrypt_base64(plaintext, key: str | bytes = Constant.AES_ENCRYPT_BASE64_SECRET_KEY):
        """
        使用 AES-ECB 模式和 PKCS7 填充对明文进行加密。

        参数:
            plaintext (str): 要加密的明文字符串。
            key (str, optional): 加密密钥，默认值为 "XwKsGlMcdPMEhR1B"。

        返回:
            str: 加密后的 Base64 编码字符串。
        """
        # 将密钥和明文转换为字节
        plaintext_bytes = plaintext.encode('utf-8')

        # 将输入密钥转换为字节
        if type(key) != bytes:
            key = key.encode('utf8')

        # 使用 PKCS7 填充明文
        padded_plaintext = pad(plaintext_bytes, AES.block_size)

        # 初始化 AES 加密器
        cipher = AES.new(key, AES.MODE_ECB)

        # 加密消息
        ciphertext = cipher.encrypt(padded_plaintext)

        # 将加密后的字节转换为 Base64 编码的字符串
        encrypted_str = base64.b64encode(ciphertext).decode('utf-8')

        return encrypted_str

    @staticmethod
    def aes_decrypt_hex(ciphertext, key=Constant.AES_ENCRYPT_SECRET_KEY):
        # 将 Hex 字符串转换为字节
        hex_bytes = binascii.unhexlify(ciphertext)

        # 将字节转换为 Base64 编码的字符串
        base64_str = base64.b64encode(hex_bytes).decode('utf-8')

        # 创建 AES 解密器
        cipher = AES.new(key, AES.MODE_ECB)

        # 将加密字符串解码为字节
        encrypted_bytes = base64.b64decode(base64_str)

        # 解密并去除 PKCS7 填充
        decrypted_bytes = cipher.decrypt(encrypted_bytes)
        decrypted_bytes = unpad(decrypted_bytes, AES.block_size)

        # 将字节转换为字符串
        return decrypted_bytes.decode('utf-8')

    @staticmethod
    def md5_encrypt(data: str) -> str:
        # 创建一个 md5 哈希对象
        md5_hash = hashlib.md5()

        # 更新 md5 哈希对象，必须将字符串编码为字节
        md5_hash.update(data.encode('utf-8'))

        # 获取加密后的 MD5 值，返回的是一个十六进制的小写字符串
        return md5_hash.hexdigest()

    @staticmethod
    def decode_base64_image(data_uri):
        """
        解码 data:image/png;base64 格式的图片数据，并返回解码后的二进制图像数据。

        参数:
            data_uri (str): 包含 Base64 编码图片数据的字符串，格式为 "data:image/png;base64,xxxxx"。
                            如果字符串不以 "data:image/png;base64," 开头，将直接将其视为 Base64 数据。

        返回:
            bytes: 解码后的二进制图像数据。
        """
        # 1. 提取 Base64 数据
        data_prefix = "data:image/png;base64,"
        if data_uri.startswith(data_prefix):
            base64_data = data_uri[len(data_prefix):]
        else:
            base64_data = data_uri

        # 2. 解码 Base64 数据
        image_data = base64.b64decode(base64_data)

        return image_data

    @staticmethod
    def picture_identify(image_data):
        # 解码 base64 数据为图像
        image_array = np.frombuffer(image_data, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        # 2. 转换到 HSV 色彩空间
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # 3. 对“白色”像素进行阈值分割
        #    注意下方范围仅为示例，实际可根据图像中白色轮廓的亮度、饱和度进行调参
        lower_white = np.array([0, 0, 255], dtype=np.uint8)  # 下界
        upper_white = np.array([0, 255, 255], dtype=np.uint8)  # 上界
        mask = cv2.inRange(hsv, lower_white, upper_white)

        # 4. 形态学操作 (可选，用于去除噪点或闭合缝隙)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (1, 1))
        mask_closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # 5. 寻找轮廓
        contours, _ = cv2.findContours(mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        puzzle_info = {}
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            # # 可以根据面积或宽高比进行过滤，避免干扰
            if area < 1600 or area > 2500:  # 过小，过大的区域可能是噪点
                continue
            puzzle_info.update({y: x})

        return puzzle_info

    @staticmethod
    def generate_random_float(integer_part, seed=None):
        """
        生成一个整数部分为 integer_part，小数点后有 decimal_places 位随机数的浮点数。

        :param integer_part: 整数部分
        :param seed: 随机数种子（可选）
        :return: 带有小数点后 14 位随机数的浮点数
        """
        if seed is not None:
            random.seed(seed)  # 设置随机种子（可选）

        random_decimal = random.random()  # 生成一个 0 到 1 之间的随机浮点数
        combined_number = integer_part + random_decimal  # 将整数部分和随机小数部分组合

        # 格式化为小数点后 14 位的字符串
        formatted_number = "{0:.14f}".format(combined_number)

        # 将字符串转换为浮点数
        return float(formatted_number)

    @staticmethod
    def report_assistant(content: str):
        # 从环境变量中获取ai配置信息
        ai_base_url = os.getenv("AI_BASE_URL")
        ai_api_key = os.getenv("AI_API_KEY")
        ai_model = os.getenv("AI_MODEL")

        # 检查必要的配置是否齐全
        if not (ai_base_url and ai_api_key and ai_model):
            raise ValueError("AI服务配置不完整, 无法自动撰写周报, 月报")

        try:
            client = OpenAI(
                base_url=ai_base_url,
                api_key=ai_api_key,
            )

            completion = client.chat.completions.create(
                model=ai_model,
                messages=[
                    ChatCompletionSystemMessageParam(
                        role="system",
                        content="你是工作实习报告助手，专门撰写不同岗位的周报和月报"
                    ),
                    ChatCompletionUserMessageParam(
                        role="user",
                        content=content
                    ),
                ],
            )

            return completion.choices[0].message.content
        except OpenAIError as e:
            return e
        except RequestException as e:
            return e

    @staticmethod
    def generate_uuid():
        # 定义一个包含所有十六进制字符的字符串
        hex_chars = "0123456789abcdef"

        # 生成长度为36的UUID
        uuid_chars = []

        for t in range(36):
            uuid_chars.append(random.choice(hex_chars))

        # 让第14个字符为4（符合UUID的标准）
        uuid_chars[14] = "4"

        # 让第19个字符为8, 9, a 或 b（符合UUID的标准）
        uuid_chars[19] = random.choice("89ab")

        # 在8, 13, 18, 23位置添加'-'
        uuid_chars[8] = uuid_chars[13] = uuid_chars[18] = uuid_chars[23] = "-"

        # 返回生成的UUID
        return "".join(uuid_chars)

    @staticmethod
    def send_request(request_class_config: dict[str, Any], url: str,
                     method: str = "get", data: dict = None,
                     response_type: str = "json", raise_for_status: bool = True, retries: int = 5,
                     delay: int = 5) -> Response | dict:
        """ 发送请求，支持重试机制 """
        # 获取logger
        logger = request_class_config.get("logger")
        # 获取业务异常
        business_exception = request_class_config.get("business_exception")
        # 获取session
        session = request_class_config.get("session")

        # 确保 method 是小写
        method = method.lower()

        # 确定请求方法
        if method not in ["get", "post", "put", "delete"]:
            logger.error(f"不支持的 HTTP 方法: {method}")
            raise business_exception

        # 根据请求方法选择合适的请求类型
        request_method = getattr(session, method)

        # 发送请求并处理异常
        for attempt in range(1, retries + 1):
            try:
                # 根据方法发送请求
                if method == "get":
                    response: Response = request_method(url, params=data)  # GET 请求的参数通过 params 传递
                else:
                    response: Response = request_method(url, json=data)  # POST、PUT、DELETE 请求的参数通过 json 传递

                # 非2xx抛出
                if raise_for_status:
                    response.raise_for_status()

                # 根据类型返回值
                if response_type.lower() == "json":
                    return response.json()

                return response

            except RequestException as e:
                logger.error(f"请求失败, 失败url: {url}, 失败原因: {e} (尝试 {attempt}/{retries})")

            # 如果已经到达最大重试次数，则返回None
            if attempt == retries:
                logger.error(f"请求失败, 失败url: {url}, 超过最大重试次数, 请求失败！")
                raise business_exception

            # 否则等待后重试
            time.sleep(delay)

        raise business_exception

    @staticmethod
    def send_email(receiver_email, body, logger):
        # 从环境变量中获取邮箱服务配置信息
        sender_email = os.getenv("SENDER_EMAIL")
        subject = os.getenv("SUBJECT")
        sender_password = os.getenv("SENDER_PASSWORD")
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = os.getenv("SMTP_PORT")

        # 检查必要的配置是否齐全
        if not (sender_email and subject and sender_password and smtp_server and smtp_port):
            logger.error("邮箱服务配置缺失, 无法发送邮件提醒")
            return

        server = None  # 在外部初始化 server
        try:
            # 设置MIME格式邮件
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = receiver_email
            msg['Subject'] = subject

            # 添加邮件正文
            msg.attach(MIMEText(body, 'plain'))

            # 连接到SMTP服务器
            server = smtplib.SMTP_SSL(smtp_server, int(smtp_port))

            # 登录邮箱
            server.login(sender_email, sender_password)

            # 发送邮件
            text = msg.as_string()
            server.sendmail(sender_email, receiver_email, text)

            logger.info(f"提醒邮件发送成功")

        except Exception as e:
            logger.error(f"提醒邮件发送失败, 失败原因: {e}")

        finally:
            if server:
                server.quit()  # 关闭连接


if __name__ == '__main__':
    pass
