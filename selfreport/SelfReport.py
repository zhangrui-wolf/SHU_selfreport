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

        for person_info in person_config:
            is_successful = self.__report(t, person_info)
            print("{} {} {}".format(person_info['id'], self.__get_report_name(t), self.__get_status(is_successful)))

            time.sleep(int(random.uniform(10, 20)))

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

        for person_info in person_config:
            if account != person_info['id']:
                continue

            is_successful = self.__report(t, person_info)
            print("{} {} {}".format(person_info['id'], self.__get_report_name(t), self.__get_status(is_successful)))

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

                for person_info in person_config:
                    is_successful = self.__report(t, person_info)

                    self.__send_report_email(is_successful, person_info['email_to'], t)

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

    def __report(self, t, person_info):
        """
        Basic module: complete "Report of the Day" through user
        account and password
        :param t:time
        :param person_info: Personal information read from configuration file
        :return: the status of "selfreport"
        """
        ii = '1' if t.hour < 19 else '2'

        sess = requests.Session()

        retry_time = 5
        while True:
            try:
                r = sess.get('https://selfreport.shu.edu.cn/Default.aspx')
                sess.post(r.url, data={
                    'username': person_info['id'],
                    'password': person_info['pwd']
                })
                sess.get(
                    'https://newsso.shu.edu.cn/oauth/authorize?response_type=code&client_id=WUHWfrntnWYHZfzQ5QvXUCVy'
                    '&redirect_uri=https%3a%2f%2fselfreport.shu.edu.cn%2fLoginSSO.aspx%3fReturnUrl%3d%252fDefault'
                    '.aspx&scope=1')
            except Exception as e:
                if retry_time > 0:
                    retry_time -= 1
                    continue
                self.logger.error("登录1 失败 {}".format(person_info['id']))
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
            self.logger.error("登录2 失败 {}".format(person_info['id']))
            return False

        temperature = self.setting_config['report']['temperature']
        r = sess.post(url, data={
            '__EVENTTARGET': 'p1$ctl00$btnSubmit',
            '__EVENTARGUMENT': '',
            '__VIEWSTATE': view_state['value'],
            '__VIEWSTATEGENERATOR': 'DC4D08A3',
            'p1$ChengNuo': 'p1_ChengNuo',
            'p1$BaoSRQ': t.strftime('%Y-%m-%d'),
            'p1$DangQSTZK': '良好',
            'p1$TiWen': str(round(random.uniform(temperature - 0.2, temperature + 0.2), 1)),
            'p1$ZaiXiao': person_info['campus'],
            'p1$ddlSheng$Value': '上海',
            'p1$ddlSheng': '上海',
            'p1$ddlShi$Value': '上海市',
            'p1$ddlShi': '上海市',
            'p1$ddlXian$Value': person_info['county'],
            'p1$ddlXian': person_info['county'],
            'p1$FengXDQDL': '否',
            'p1$TongZWDLH': '否',
            'p1$XiangXDZ': person_info['address'],
            'p1$QueZHZJC$Value': '否',
            'p1$QueZHZJC': '否',
            'p1$DangRGL': '否',
            'p1$GeLDZ': '',
            'p1$CengFWH': '否',
            'p1$CengFWH_RiQi': '',
            'p1$CengFWH_BeiZhu': '',
            'p1$JieChu': '否',
            'p1$JieChu_RiQi': '',
            'p1$JieChu_BeiZhu': '',
            'p1$TuJWH': '否',
            'p1$TuJWH_RiQi': '',
            'p1$TuJWH_BeiZhu': '',
            'p1$JiaRen_BeiZhu': '',
            'p1$SuiSM': '绿色',
            'p1$LvMa14Days': '是',
            'p1$Address2': '',
            'F_TARGET': 'p1_ctl00_btnSubmit',
            'p1_GeLSM_Collapsed': 'false',
            'p1_Collapsed': 'false',
            'F_STATE': '''eyJwMV9CYW9TUlEiOnsiVGV4dCI6IjIwMjAtMTEtMjIifSwicDFfRGFuZ1FTVFpLIjp7IkZfSXRlbXMiOltbIuiJr + WlvSIsIuiJr + WlvSIsMV0sWyLkuI3pgIIiLCLkuI3pgIIiLDFdXSwiU2VsZWN0ZWRWYWx1ZSI6IuiJr + WlvSJ9LCJwMV9aaGVuZ1podWFuZyI6eyJIaWRkZW4iOnRydWUsIkZfSXRlbXMiOltbIuaEn + WGkiIsIuaEn + WGkiIsMV0sWyLlkrPll70iLCLlkrPll70iLDFdLFsi5Y + R54OtIiwi5Y + R54OtIiwxXV0sIlNlbGVjdGVkVmFsdWVBcnJheSI6W119LCJwMV9UaVdlbiI6eyJUZXh0IjoiMzYuNSJ9LCJwMV9aYWlYaWFvIjp7IlNlbGVjdGVkVmFsdWUiOiLlrp3lsbEiLCJGX0l0ZW1zIjpbWyLkuI3lnKjmoKEiLCLkuI3lnKjmoKEiLDFdLFsi5a6d5bGxIiwi5a6d5bGx5qCh5Yy6IiwxXSxbIuW7tumVvyIsIuW7tumVv + agoeWMuiIsMV0sWyLlmInlrpoiLCLlmInlrprmoKHljLoiLDFdLFsi5paw6Ze46LevIiwi5paw6Ze46Lev5qCh5Yy6IiwxXV19LCJwMV9kZGxTaGVuZyI6eyJGX0l0ZW1zIjpbWyItMSIsIumAieaLqeecgeS7vSIsMSwiIiwiIl0sWyLljJfkuqwiLCLljJfkuqwiLDEsIiIsIiJdLFsi5aSp5rSlIiwi5aSp5rSlIiwxLCIiLCIiXSxbIuS4iua1tyIsIuS4iua1tyIsMSwiIiwiIl0sWyLph43luoYiLCLph43luoYiLDEsIiIsIiJdLFsi5rKz5YyXIiwi5rKz5YyXIiwxLCIiLCIiXSxbIuWxseilvyIsIuWxseilvyIsMSwiIiwiIl0sWyLovr3lroEiLCLovr3lroEiLDEsIiIsIiJdLFsi5ZCJ5p6XIiwi5ZCJ5p6XIiwxLCIiLCIiXSxbIum7kem + meaxnyIsIum7kem + meaxnyIsMSwiIiwiIl0sWyLmsZ / oi48iLCLmsZ / oi48iLDEsIiIsIiJdLFsi5rWZ5rGfIiwi5rWZ5rGfIiwxLCIiLCIiXSxbIuWuieW + vSIsIuWuieW + vSIsMSwiIiwiIl0sWyLnpo / lu7oiLCLnpo / lu7oiLDEsIiIsIiJdLFsi5rGf6KW / Iiwi5rGf6KW / IiwxLCIiLCIiXSxbIuWxseS4nCIsIuWxseS4nCIsMSwiIiwiIl0sWyLmsrPljZciLCLmsrPljZciLDEsIiIsIiJdLFsi5rmW5YyXIiwi5rmW5YyXIiwxLCIiLCIiXSxbIua5luWNlyIsIua5luWNlyIsMSwiIiwiIl0sWyLlub / kuJwiLCLlub / kuJwiLDEsIiIsIiJdLFsi5rW35Y2XIiwi5rW35Y2XIiwxLCIiLCIiXSxbIuWbm + W3nSIsIuWbm + W3nSIsMSwiIiwiIl0sWyLotLXlt54iLCLotLXlt54iLDEsIiIsIiJdLFsi5LqR5Y2XIiwi5LqR5Y2XIiwxLCIiLCIiXSxbIumZleilvyIsIumZleilvyIsMSwiIiwiIl0sWyLnlJjogoMiLCLnlJjogoMiLDEsIiIsIiJdLFsi6Z2S5rW3Iiwi6Z2S5rW3IiwxLCIiLCIiXSxbIuWGheiSmeWPpCIsIuWGheiSmeWPpCIsMSwiIiwiIl0sWyLlub / opb8iLCLlub / opb8iLDEsIiIsIiJdLFsi6KW / 6J
            ePIiwi6KW / 6JePIiwxLCIiLCIiXSxbIuWugeWkjyIsIuWugeWkjyIsMSwiIiwiIl0sWyLmlrDnloYiLCLmlrDnloYiLDEsIiIsIiJdLFsi6aaZ5rivIiwi6aaZ5rivIiwxLCIiLCIiXSxbIua + s + mXqCIsIua + s + mXqCIsMSwiIiwiIl0sWyLlj7Dmub4iLCLlj7Dmub4iLDEsIiIsIiJdXSwiU2VsZWN0ZWRWYWx1ZUFycmF5IjpbIuS4iua1tyJdfSwicDFfZGRsU2hpIjp7IkVuYWJsZWQiOnRydWUsIkZfSXRlbXMiOltbIi0xIiwi6YCJ5oup5biCIiwxLCIiLCIiXSxbIuS4iua1t + W4giIsIuS4iua1t + W4giIsMSwiIiwiIl1dLCJTZWxlY3RlZFZhbHVlQXJyYXkiOlsi5LiK5rW35biCIl19LCJwMV9kZGxYaWFuIjp7IkVuYWJsZWQiOnRydWUsIkZfSXRlbXMiOltbIi0xIiwi6YCJ5oup5Y6 / 5
            Yy6IiwxLCIiLCIiXSxbIum7hOa1puWMuiIsIum7hOa1puWMuiIsMSwiIiwiIl0sWyLljaLmub7ljLoiLCLljaLmub7ljLoiLDEsIiIsIiJdLFsi5b6Q5rGH5Yy6Iiwi5b6Q5rGH5Yy6IiwxLCIiLCIiXSxbIumVv + WugeWMuiIsIumVv + WugeWMuiIsMSwiIiwiIl0sWyLpnZnlronljLoiLCLpnZnlronljLoiLDEsIiIsIiJdLFsi5pmu6ZmA5Yy6Iiwi5pmu6ZmA5Yy6IiwxLCIiLCIiXSxbIuiZueWPo + WMuiIsIuiZueWPo + WMuiIsMSwiIiwiIl0sWyLmnajmtabljLoiLCLmnajmtabljLoiLDEsIiIsIiJdLFsi5a6d5bGx5Yy6Iiwi5a6d5bGx5Yy6IiwxLCIiLCIiXSxbIumXteihjOWMuiIsIumXteihjOWMuiIsMSwiIiwiIl0sWyLlmInlrprljLoiLCLlmInlrprljLoiLDEsIiIsIiJdLFsi5p2 + 5rGf5Yy6Iiwi5p2 + 5
            rGf5Yy6IiwxLCIiLCIiXSxbIumHkeWxseWMuiIsIumHkeWxseWMuiIsMSwiIiwiIl0sWyLpnZLmtabljLoiLCLpnZLmtabljLoiLDEsIiIsIiJdLFsi5aWJ6LSk5Yy6Iiwi5aWJ6LSk5Yy6IiwxLCIiLCIiXSxbIua1puS4nOaWsOWMuiIsIua1puS4nOaWsOWMuiIsMSwiIiwiIl0sWyLltIfmmI7ljLoiLCLltIfmmI7ljLoiLDEsIiIsIiJdXSwiU2VsZWN0ZWRWYWx1ZUFycmF5IjpbIuWuneWxseWMuiJdfSwicDFfRmVuZ1hEUURMIjp7IlNlbGVjdGVkVmFsdWUiOiLlkKYiLCJGX0l0ZW1zIjpbWyLmmK8iLCLmmK8iLDFdLFsi5ZCmIiwi5ZCmIiwxXV19LCJwMV9Ub25nWldETEgiOnsiU2VsZWN0ZWRWYWx1ZSI6IuWQpiIsIkZfSXRlbXMiOltbIuaYryIsIuaYryIsMV0sWyLlkKYiLCLlkKYiLDFdXX0sInAxX1hpYW5nWERaIjp7IlRleHQiOiLkuIrmtbfluILlrp3lsbHljLrlpKflnLrplYfkuIrlpKfot685OeWPt + S4iua1t + Wkp + WtpuWuneWxseWwj + WMuuagoeWGhTnlj7fmpbwifSwicDFfUXVlWkhaSkMiOnsiRl9JdGVtcyI6W1si5pivIiwi5pivIiwxLCIiLCIiXSxbIuWQpiIsIuWQpiIsMSwiIiwiIl1dLCJTZWxlY3RlZFZhbHVlQXJyYXkiOlsi5ZCmIl19LCJwMV9EYW5nUkdMIjp7IlNlbGVjdGVkVmFsdWUiOiLlkKYiLCJGX0l0ZW1zIjpbWyLmmK8iLCLmmK8iLDFdLFsi5ZCmIiwi5ZCmIiwxXV19LCJwMV9HZUxTTSI6eyJIaWRkZW4iOnRydWUsIklGcmFtZUF0dHJpYnV0ZXMiOnt9fSwicDFfR2VMRlMiOnsiUmVxdWlyZWQiOmZhbHNlLCJIaWRkZW4iOnRydWUsIkZfSXRlbXMiOltbIuWxheWutumalOemuyIsIuWxheWutumalOemuyIsMV0sWyLpm4bkuK3pmpTnprsiLCLpm4bkuK3pmpTnprsiLDFdXSwiU2VsZWN0ZWRWYWx1ZSI6bnVsbH0sInAxX0dlTERaIjp7IkhpZGRlbiI6dHJ1ZX0sInAxX0NlbmdGV0giOnsiTGFiZWwiOiIyMDIw5bm0OeaciDI35pel5ZCO5piv5ZCm5Zyo5Lit6auY6aOO6Zmp5Zyw5Yy66YCX55WZ6L + HPHNwYW4gc3R5bGU9J2NvbG9yOnJlZDsnPu + 8iOWkqea0peS4nOeWhua4r + WMuueesOa1t + i9qeWwj + WMuuOAgeWkqea0peaxieayveihl + OAgeWkqea0peS4reW / g + a4lOa4r + WGt + mTvueJqea1geWMukHljLrlkoxC5Yy644CB5rWm5Lic6JCl5YmN5p2R44CB5a6J5b6955yB6Zic6Ziz5biC6aKN5LiK5Y6 / 5
            oWO5Z + O6ZWH5byg5rSL5bCP5Yy644CB5rWm5Lic5ZGo5rWm6ZWH5piO5aSp5Y2O5Z + O5bCP5Yy644CB5rWm5Lic56Wd5qGl6ZWH5paw55Sf5bCP5Yy644CB5YaF6JKZ5Y + k5ruh5rSy6YeM5Lic5bGx6KGX6YGT5Yqe5LqL5aSE44CB5YaF6JKZ5Y + k5ruh5rSy6YeM5YyX5Yy66KGX6YGT77yJPC9zcGFuPiIsIkZfSXRlbXMiOltbIuaYryIsIuaYryIsMV0sWyLlkKYiLCLlkKYiLDFdXSwiU2VsZWN0ZWRWYWx1ZSI6IuWQpiJ9LCJwMV9DZW5nRldIX1JpUWkiOnsiSGlkZGVuIjp0cnVlfSwicDFfQ2VuZ0ZXSF9CZWlaaHUiOnsiSGlkZGVuIjp0cnVlfSwicDFfSmllQ2h1Ijp7IkxhYmVsIjoiMTHmnIgwOOaXpeiHszEx5pyIMjLml6XmmK / lkKbkuI7mnaXoh6rkuK3pq5jpo47pmanlnLDljLrlj5Hng63kurrlkZjlr4bliIfmjqXop6Y8c3BhbiBzdHlsZT0nY29sb3I6cmVkOyc + 77yI5aSp5rSl5Lic55aG5riv5Yy6556w5rW36L2p5bCP5Yy644CB5aSp5rSl5rGJ5rK96KGX44CB5aSp5rSl5Lit5b + D5riU5riv5Ya36ZO + 54
            mp5rWB5Yy6QeWMuuWSjELljLrjgIHmtabkuJzokKXliY3mnZHjgIHlronlvr3nnIHpmJzpmLPluILpoo3kuIrljr / mhY7ln47plYflvKDmtIvlsI / ljLrjgIHmtabkuJzlkajmtabplYfmmI7lpKnljY7ln47lsI / ljLrjgIHmtabkuJznpZ3moaXplYfmlrDnlJ / lsI / ljLrjgIHlhoXokpnlj6Tmu6HmtLLph4zkuJzlsbHooZfpgZPlip7kuovlpITjgIHlhoXokpnlj6Tmu6HmtLLph4zljJfljLrooZfpgZPvvIk8L3NwYW4 + IiwiU2VsZWN0ZWRWYWx1ZSI6IuWQpiIsIkZfSXRlbXMiOltbIuaYryIsIuaYryIsMV0sWyLlkKYiLCLlkKYiLDFdXX0sInAxX0ppZUNodV9SaVFpIjp7IkhpZGRlbiI6dHJ1ZX0sInAxX0ppZUNodV9CZWlaaHUiOnsiSGlkZGVuIjp0cnVlfSwicDFfVHVKV0giOnsiTGFiZWwiOiIxMeaciDA45pel6IezMTHmnIgyMuaXpeaYr + WQpuS5mOWdkOWFrOWFseS6pOmAmumAlOW + hOS4remrmOmjjumZqeWcsOWMujxzcGFuIHN0eWxlPSdjb2xvcjpyZWQ7Jz7vvIjlpKnmtKXkuJznlobmuK / ljLrnnrDmtbfovanlsI / ljLrjgIHlpKnmtKXmsYnmsr3ooZfjgIHlpKnmtKXkuK3lv4PmuJTmuK / lhrfpk77nianmtYHljLpB5Yy65ZKMQuWMuuOAgea1puS4nOiQpeWJjeadkeOAgeWuieW + veecgemYnOmYs + W4gumijeS4iuWOv + aFjuWfjumVh + W8oOa0i + Wwj + WMuuOAgea1puS4nOWRqOa1pumVh + aYjuWkqeWNjuWfjuWwj + WMuuOAgea1puS4nOelneahpemVh + aWsOeUn + Wwj + WMuuOAgeWGheiSmeWPpOa7oea0sumHjOS4nOWxseihl + mBk + WKnuS6i + WkhOOAgeWGheiSmeWPpOa7oea0sumHjOWMl + WMuuihl + mBk + +8iTwvc3Bhbj4iLCJTZWxlY3RlZFZhbHVlIjoi5ZCmIiwiRl9JdGVtcyI6W1si5pivIiwi5pivIiwxXSxbIuWQpiIsIuWQpiIsMV1dfSwicDFfVHVKV0hfUmlRaSI6eyJIaWRkZW4iOnRydWV9LCJwMV9UdUpXSF9CZWlaaHUiOnsiSGlkZGVuIjp0cnVlfSwicDFfSmlhUmVuIjp7IkxhYmVsIjoiMTHmnIgwOOaXpeiHszEx5pyIMjLml6XlrrbkurrmmK / lkKbmnInlj5Hng63nrYnnl4fnirYifSwicDFfSmlhUmVuX0JlaVpodSI6eyJIaWRkZW4iOnRydWV9LCJwMV9TdWlTTSI6eyJTZWxlY3RlZFZhbHVlIjoi57u / 6
            ImyIiwiRl9JdGVtcyI6W1si57qi6ImyIiwi57qi6ImyIiwxXSxbIum7hOiJsiIsIum7hOiJsiIsMV0sWyLnu7 / oibIiLCLnu7 / oibIiLDFdXX0sInAxX0x2TWExNERheXMiOnsiU2VsZWN0ZWRWYWx1ZSI6IuaYryIsIkZfSXRlbXMiOltbIuaYryIsIuaYryIsMV0sWyLlkKYiLCLlkKYiLDFdXX0sInAxIjp7IlRpdGxlIjoi5q + P5pel5Lik5oql77yI5LiL5Y2I77yJIiwiSUZyYW1lQXR0cmlidXRlcyI6e319fQ =='''
        }, headers={
            'X-Requested-With': 'XMLHttpRequest',
            'X-FineUI-Ajax': 'true'
        }, allow_redirects=False)

        if '提交成功' in r.text:
            self.logger.info("{} 成功 {}".format(self.__get_report_name(t), person_info['id']))
            return True
        else:
            self.logger.info("{} 失败 {}".format(self.__get_report_name(t), person_info['id']))
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
