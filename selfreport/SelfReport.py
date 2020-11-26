# -- coding: utf-8 --

import os
import re
import time
import yaml
import random
import base64
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
        temperature = str(round(random.uniform(temperature - 0.2, temperature + 0.2), 1))
        f_state = '''{"p1_BaoSRQ":{"Text":"%s"},"p1_DangQSTZK":{"F_Items":[["良好","良好",1],["不适","不适",1]],"SelectedValue":"良好"},"p1_ZhengZhuang":{"Hidden":true,"F_Items":[["感冒","感冒",1],["咳嗽","咳嗽",1],["发热","发热",1]],"SelectedValueArray":[]},"p1_TiWen":{"Text":"%s"},"p1_ZaiXiao":{"SelectedValue":"%s","F_Items":[["不在校","不在校",1],["宝山","宝山校区",1],["延长","延长校区",1],["嘉定","嘉定校区",1],["新闸路","新闸路校区",1]]},"p1_ddlSheng":{"F_Items":[["-1","选择省份",1,"",""],["北京","北京",1,"",""],["天津","天津",1,"",""],["上海","上海",1,"",""],["重庆","重庆",1,"",""],["河北","河北",1,"",""],["山西","山西",1,"",""],["辽宁","辽宁",1,"",""],["吉林","吉林",1,"",""],["黑龙江","黑龙江",1,"",""],["江苏","江苏",1,"",""],["浙江","浙江",1,"",""],["安徽","安徽",1,"",""],["福建","福建",1,"",""],["江西","江西",1,"",""],["山东","山东",1,"",""],["河南","河南",1,"",""],["湖北","湖北",1,"",""],["湖南","湖南",1,"",""],["广东","广东",1,"",""],["海南","海南",1,"",""],["四川","四川",1,"",""],["贵州","贵州",1,"",""],["云南","云南",1,"",""],["陕西","陕西",1,"",""],["甘肃","甘肃",1,"",""],["青海","青海",1,"",""],["内蒙古","内蒙古",1,"",""],["广西","广西",1,"",""],["西藏","西藏",1,"",""],["宁夏","宁夏",1,"",""],["新疆","新疆",1,"",""],["香港","香港",1,"",""],["澳门","澳门",1,"",""],["台湾","台湾",1,"",""]],"SelectedValueArray":["%s"]},"p1_ddlShi":{"Enabled":true,"F_Items":[["-1","选择市",1,"",""],["上海市","上海市",1,"",""]],"SelectedValueArray":["%s"]},"p1_ddlXian":{"Enabled":true,"F_Items":[["-1","选择县区",1,"",""],["黄浦区","黄浦区",1,"",""],["卢湾区","卢湾区",1,"",""],["徐汇区","徐汇区",1,"",""],["长宁区","长宁区",1,"",""],["静安区","静安区",1,"",""],["普陀区","普陀区",1,"",""],["虹口区","虹口区",1,"",""],["杨浦区","杨浦区",1,"",""],["宝山区","宝山区",1,"",""],["闵行区","闵行区",1,"",""],["嘉定区","嘉定区",1,"",""],["松江区","松江区",1,"",""],["金山区","金山区",1,"",""],["青浦区","青浦区",1,"",""],["奉贤区","奉贤区",1,"",""],["浦东新区","浦东新区",1,"",""],["崇明区","崇明区",1,"",""]],"SelectedValueArray":["%s"]},"p1_FengXDQDL":{"SelectedValue":"否","F_Items":[["是","是",1],["否","否",1]]},"p1_TongZWDLH":{"SelectedValue":"否","F_Items":[["是","是",1],["否","否",1]]},"p1_XiangXDZ":{"Text":"%s"},"p1_QueZHZJC":{"F_Items":[["是","是",1,"",""],["否","否",1,"",""]],"SelectedValueArray":["否"]},"p1_DangRGL":{"SelectedValue":"否","F_Items":[["是","是",1],["否","否",1]]},"p1_GeLSM":{"Hidden":true,"IFrameAttributes":{}},"p1_GeLFS":{"Required":false,"Hidden":true,"F_Items":[["居家隔离","居家隔离",1],["集中隔离","集中隔离",1]],"SelectedValue":null},"p1_GeLDZ":{"Hidden":true},"p1_CengFWH":{"Label":"2020年9月27日后是否在中高风险地区逗留过<span style='color:red;'>（天津东疆港区瞰海轩小区、天津汉沽街、天津中心渔港冷链物流区A区和B区、浦东营前村、安徽省阜阳市颍上县慎城镇张洋小区、浦东周浦镇明天华城小区、浦东祝桥镇新生小区、内蒙古满洲里东山街道办事处、内蒙古满洲里北区街道）</span>","F_Items":[["是","是",1],["否","否",1]],"SelectedValue":"否"},"p1_CengFWH_RiQi":{"Hidden":true},"p1_CengFWH_BeiZhu":{"Hidden":true},"p1_JieChu":{"Label":"11月08日至11月22日是否与来自中高风险地区发热人员密切接触<span style='color:red;'>（天津东疆港区瞰海轩小区、天津汉沽街、天津中心渔港冷链物流区A区和B区、浦东营前村、安徽省阜阳市颍上县慎城镇张洋小区、浦东周浦镇明天华城小区、浦东祝桥镇新生小区、内蒙古满洲里东山街道办事处、内蒙古满洲里北区街道）</span>","SelectedValue":"否","F_Items":[["是","是",1],["否","否",1]]},"p1_JieChu_RiQi":{"Hidden":true},"p1_JieChu_BeiZhu":{"Hidden":true},"p1_TuJWH":{"Label":"11月08日至11月22日是否乘坐公共交通途径中高风险地区<span style='color:red;'>（天津东疆港区瞰海轩小区、天津汉沽街、天津中心渔港冷链物流区A区和B区、浦东营前村、安徽省阜阳市颍上县慎城镇张洋小区、浦东周浦镇明天华城小区、浦东祝桥镇新生小区、内蒙古满洲里东山街道办事处、内蒙古满洲里北区街道）</span>","SelectedValue":"否","F_Items":[["是","是",1],["否","否",1]]},"p1_TuJWH_RiQi":{"Hidden":true},"p1_TuJWH_BeiZhu":{"Hidden":true},"p1_JiaRen":{"Label":"11月08日至11月22日家人是否有发热等症状"},"p1_JiaRen_BeiZhu":{"Hidden":true},"p1_SuiSM":{"SelectedValue":"绿色","F_Items":[["红色","红色",1],["黄色","黄色",1],["绿色","绿色",1]]},"p1_LvMa14Days":{"SelectedValue":"是","F_Items":[["是","是",1],["否","否",1]]},"p1":{"Title":"每日两报（%s）","IFrameAttributes":{}}}''' % (t.strftime('%Y-%m-%d'), temperature, person_info['campus'], '上海', '上海市', person_info['county'], person_info['address'], self.__get_report_name(t))
        f_state = base64.b64encode(bytes(f_state, encoding='utf-8'))
        r = sess.post(url, data={
            '__EVENTTARGET': 'p1$ctl00$btnSubmit',
            '__EVENTARGUMENT': '',
            '__VIEWSTATE': view_state['value'],
            '__VIEWSTATEGENERATOR': 'DC4D08A3',
            'p1$ChengNuo': 'p1_ChengNuo',
            'p1$BaoSRQ': t.strftime('%Y-%m-%d'),
            'p1$DangQSTZK': '良好',
            'p1$TiWen': temperature,
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
            'F_STATE': f_state
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
        return "每日两报（上午）" if morning_hour <= t.hour < night_hour else "每日两报（下午）"

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
