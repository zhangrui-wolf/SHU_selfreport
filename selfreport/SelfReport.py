# -- coding: utf-8 --

import os
import re
import time
import yaml
import random
import smtplib
import logging
import requests
import datetime as dt
from pathlib import Path
from bs4 import BeautifulSoup
from email.message import EmailMessage
from logging.handlers import TimedRotatingFileHandler


class SelfReport(object):
    def __init__(self, setting_config_path, person_config_path, save_log_dir, log_file_name):
        """
        Initialize the class named SelfReport.
        :param setting_config_path: path of setting_config.yaml
        :param person_config_path: path of person_config.yaml
        :param save_log_dir: directory where logs are stored
        :log_file_name: the name prefix of the log file
        """
        def path_check(path):
            path_obj = Path(path)
            if not path_obj.exists():
                print("Error: {} does not exist!".format(path))
                exit(1)
            if not path_obj.is_file():
                print("Error: {} is not a file path!".format(path))
                exit(1)

        def setup_log(log_dir, log_name):
            res = logging.getLogger(log_name)
            log_path = os.path.join(log_dir, log_name)
            res.setLevel(logging.INFO)
            file_handler = TimedRotatingFileHandler(filename=log_path, when="MIDNIGHT", interval=1, backupCount=30)
            file_handler.suffix = "%Y-%m-%d.log"
            file_handler.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}.log$")
            file_handler.setFormatter(logging.Formatter("%(levelname)s %(asctime)s %(message)s"))
            res.addHandler(file_handler)
            return res

        path_check(setting_config_path)
        path_check(person_config_path)

        self.setting_config_path = setting_config_path
        self.person_config_path = person_config_path

        self.setting_config = self.__load_setting_config()

        if not os.path.exists(save_log_dir):
            os.makedirs(save_log_dir)

        self.save_log_dir = save_log_dir
        self.log_file_name = log_file_name

        self.logger = setup_log(save_log_dir, log_file_name)

    def test_send_email(self, email_to):
        """
        Test the module for sending mail.
        :param email_to: account to receive test email
        :return: no return
        """
        subject = "发送模块测试邮件"
        message = "配置文件中的email模块设置正常。\n<br/>"
        if self.setting_config['report']['send_email']:
            message += "主人您现在的设置已经开启邮件提醒功能，程序将会在每日一报后通过邮件告诉主人您！"
        else:
            message += "主人您还没有开启发送每日一报报送状态的邮件提醒功能，如果需要，只需将report中的send_email选项设为true即可。感谢主人的使用！"
        self.__send_mail(email_to, subject, message)
        exit(0)

    def test_all_accounts(self):
        """
        Test whether all accounts in setting_config.yaml are correct. When
        testing, each account has an interval of 30-60 seconds.
        :return: no return
        """
        t = self.__get_time()

        person_config = self.__load_config(self.person_config_path)

        for user in person_config:
            is_successful = self.__report(t, user['id'], user['pwd'])
            print("{} {} {}".format(user['id'], self.__get_report_name(t), self.__get_status(is_successful)))

            time.sleep(int(random.uniform(30, 60)))

        exit(0)

    def test_single_account(self, account):
        """
        Used to test the newly added account. Find the input parameter "account"
        in setting_config.yaml to test whether the account is correct.
        :param account: account used for testing
        :return: no return
        """
        t = self.__get_time()

        person_config = self.__load_config(self.person_config_path)

        for user in person_config:
            if account != user['id']:
                continue

            is_successful = self.__report(t, user['id'], user['pwd'])
            print("{} {} {}".format(user['id'], self.__get_report_name(t), self.__get_status(is_successful)))

            break

        exit(0)

    def auto_report(self):
        """
        Automatically complete "selfreport".
        :return: no return
        """

        while True:
            t = self.__get_time()

            if t.hour == 0 and t.minute == 0:
                self.setting_config = self.__load_setting_config()

            if (t.hour == self.setting_config['report']['morning_hour'] and
                t.minute in [self.setting_config['report']['morning_minute'],
                             self.setting_config['report']['morning_minute'] + 1]) or (
                    t.hour == self.setting_config['report']['night_hour'] and
                    t.minute in [self.setting_config['report']['night_minute'],
                                 self.setting_config['report']['night_minute'] + 1]):

                person_config = self.__load_config(self.person_config_path)

                for user in person_config:
                    is_successful = self.__report(t, user['id'], user['pwd'])

                    self.__send_report_email(is_successful, user['email_to'], t)

                    time.sleep(int(random.uniform(30, 60)))

                time.sleep(60)

            if self.setting_config['manager']['send_email']:
                if (t.hour == self.setting_config['manager']['hour'] and
                        t.minute in [self.setting_config['manager']['minute'],
                                     self.setting_config['manager']['minute'] + 1]):
                    self.__send_mail(self.setting_config['manager']['email_to'], "{}月{}日 日志".format(t.month, t.day),
                                     self.__read_file_as_str(self.__get_log_file_path()))

                    time.sleep(60)

            time.sleep(60)

    def __load_setting_config(self):
        """
        Load setting_config.yaml, and automatically correct errors after loading.
        :return: no return
        """
        setting_config = self.__load_config(self.setting_config_path)

        if (not setting_config['email']['from'] or not setting_config['email']['username'] or
                not setting_config['email']['password'] or not setting_config['email']['smtp'] or
                not setting_config['email']['port']):
            setting_config['report']['send_email'] = False

        if setting_config['report']['morning_hour'] < 6 or setting_config['report']['morning_hour'] > 20:
            setting_config['report']['morning_hour'] = 7
        if setting_config['report']['morning_minute'] < 0 or setting_config['report']['morning_minute'] >= 60:
            setting_config['report']['morning_minute'] = 30
        if setting_config['report']['night_hour'] < 19 or setting_config['report']['night_hour'] > 23:
            setting_config['report']['night_hour'] = 20
        if setting_config['report']['night_minute'] < 0 or setting_config['report']['night_minute'] >= 60:
            setting_config['report']['night_minute'] = 30

        if setting_config['report']['temperature'] < 35 or setting_config['report']['temperature'] >= 37.3:
            setting_config['report']['temperature'] = 36.5

        if setting_config['manager']['send_email']:
            if not setting_config['manager']['email_to']:
                setting_config['manager']['send_email'] = False
            if setting_config['manager']['hour'] < 0 or setting_config['manager']['hour'] > 23:
                setting_config['manager']['hour'] = 22
            if setting_config['manager']['minute'] < 0 or setting_config['manager']['minute'] >= 60:
                setting_config['manager']['minute'] = 30

        return setting_config

    @staticmethod
    def __load_config(config_path):
        """
        Load configuration file.
        :param config_path: the path of the configuration file
        :return: configuration parameters
        """
        with open(config_path, encoding='utf8') as f:
            return yaml.load(f, Loader=yaml.FullLoader)

    @staticmethod
    def __get_time():
        """
        Get the current system time.
        :return: time
        """
        t = dt.datetime.utcnow()
        t = t + dt.timedelta(hours=8)
        return t

    def __report(self, t, username, password):
        """
        Basic module: complete "Report of the Day" through user
        account and password
        :param t:time
        :param username: account
        :param password: password
        :return: the status of "selfreport"
        """
        ii = '1' if t.hour < 19 else '2'

        sess = requests.Session()

        retry_time = 5
        while True:
            try:
                r = sess.get('https://selfreport.shu.edu.cn/Default.aspx')
                sess.post(r.url, data={
                    'username': username,
                    'password': password
                })
                sess.get(
                    'https://newsso.shu.edu.cn/oauth/authorize?response_type=code&client_id=WUHWfrntnWYHZfzQ5QvXUCVy'
                    '&redirect_uri=https%3a%2f%2fselfreport.shu.edu.cn%2fLoginSSO.aspx%3fReturnUrl%3d%252fDefault'
                    '.aspx&scope=1')
            except Exception as e:
                if retry_time > 0:
                    retry_time -= 1
                    continue
                self.logger.error("登录1 失败 {}".format(username))
                return False
            break

        url = f'https://selfreport.shu.edu.cn/XueSFX/HalfdayReport.aspx?day={t.year}-{t.month}-{t.day}&t={ii}'

        retry_time = 5
        while True:
            try:
                r = sess.get(url)
            except Exception:
                if retry_time > 0:
                    retry_time -= 1
                    continue
                self.logger.error("网页获取 失败 {}".format(url))
                return False
            break

        soup = BeautifulSoup(r.text, 'html.parser')
        view_state = soup.find('input', attrs={'name': '__VIEWSTATE'})

        if view_state is None:
            self.logger.error("登录2 失败 {}".format(username))
            return False

        temperature = self.setting_config['report']['temperature']
        r = sess.post(url, data={
            '__EVENTTARGET': 'p1$ctl00$btnSubmit',
            '__VIEWSTATE': view_state['value'],
            '__VIEWSTATEGENERATOR': 'DC4D08A3',
            'p1$ChengNuo': 'p1_ChengNuo',
            'p1$BaoSRQ': t.strftime('%Y-%m-%d'),
            'p1$DangQSTZK': '良好',
            'p1$TiWen': str(round(random.uniform(temperature - 0.2, temperature + 0.2), 1)),
            'p1$SuiSM': '绿色',
            'p1$ShiFJC': ['早餐', '午餐', '晚餐'],
            'F_TARGET': 'p1_ctl00_btnSubmit',
            'p1_Collapsed': 'false',
        }, headers={
            'X-Requested-With': 'XMLHttpRequest',
            'X-FineUI-Ajax': 'true'
        }, allow_redirects=False)

        if '提交成功' in r.text:
            self.logger.info("{} 成功 {}".format(self.__get_report_name(t), username))
            return True
        else:
            self.logger.info("{} 失败 {}".format(self.__get_report_name(t), username))
            return False

    def __send_report_email(self, is_successful, email_to, t):
        """
        Mail sending module, the content is the status of "selfreport".
        :param is_successful: the status of "selfreport"
        :param email_to: account to receive mail
        :param t: time
        :return: no return
        """
        if self.setting_config['report']['send_email']:
            self.__send_mail(email_to, self.__get_subject(is_successful, t),
                             self.__get_report_message(is_successful, t))

    def __send_mail(self, email_to, subject, message):
        """
        Basic module for sending emails.
        :param email_to: account to receive mail
        :param subject: subject of the email message
        :param message: message of the email
        :return: no return
        """
        msg = self.__get_email_msg([email_to], subject, message)

        sender_config = self.setting_config['email']

        retry_time = 5
        while True:
            try:
                server = smtplib.SMTP_SSL(
                    sender_config['smtp'],
                    port=sender_config['port'])
                server.login(sender_config['username'], sender_config['password'])
                server.send_message(msg)
                server.close()
                self.logger.info("发送邮件 成功 {}".format(email_to))
            except smtplib.SMTPException:
                if retry_time > 0:
                    retry_time -= 1
                    continue
                self.logger.error("发送邮件 失败 {}".format(email_to))
            break

    def __get_email_msg(self, email_to, subject, message):
        """
        Get email message.
        :param email_to: account to receive email
        :param subject: subject of the email message
        :param message: message of the email
        :return: email message
        """
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = self.setting_config['email']['from']
        msg['To'] = ', '.join(email_to)
        msg.set_content(message)
        return msg

    def __get_subject(self, is_successful, t):
        """
        Get subject of the email message
        :param is_successful: the status of "selfreport"
        :param t: time
        :return: subject of the email message
        """
        return "{}月{}日{}提交{}".format(
            t.month, t.day, self.__get_report_name(t), self.__get_status(is_successful))

    @staticmethod
    def __get_status(is_true):
        """
        Convert bool value to Chinese text.
        :param is_true: bool value
        :return: the explanation of the input parameter "is_true"
        """
        return "成功" if is_true else "失败"

    def __get_report_name(self, t):
        """
        According to the time to determine whether it is "晨报"
        or "晚报"
        :param t: time
        :return: report name
        """
        morning_hour = self.setting_config["report"]["morning_hour"]
        night_hour = self.setting_config["report"]["night_hour"]
        return "晨报" if morning_hour <= t.hour < night_hour else "晚报"

    def __get_report_message(self, is_successful, t):
        """
        Get the message of email
        :param is_successful: the status of the "selfreport"
        :param t: time
        :return: the message of email
        """
        if is_successful:
            return "{}报送成功!".format(self.__get_report_name(t))
        else:
            return '''{}报送失败，动动您的小手指，登录每日一报查看是否真的失败了!<br/><br/>
            如果显示报送成功，那是学校服务器问题，请忽略。<br/><br/>
            如果显示报送失败，可能为学校服务器错误、登录界面进行了更新，或者是账号密码有误，请找到管理员大大，让他及时更新程序。<br/><br/>
            '''.format(self.__get_report_name(t))

    @staticmethod
    def __read_file_as_str(file_path):
        """
        Read the content of the log file and save it as a python string type.
        :param file_path: the path of the log file
        :return: python string
        """
        if not Path(file_path).exists():
            all_the_text = "无日志"
        else:
            with open(file_path) as f:
                all_the_text = f.read()

        return all_the_text

    def __get_log_file_path(self):
        return os.path.join(self.save_log_dir, self.log_file_name)
