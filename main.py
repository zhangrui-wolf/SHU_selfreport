# -- coding: utf-8 --
import argparse

from selfreport.SelfReport import SelfReport

if __name__ == "__main__":
    setting_config_path = "configs/setting_config.yaml"
    person_config_path = "configs/person_config.yaml"
    save_log_dir = "log/"

    self_report = SelfReport(setting_config_path, person_config_path, save_log_dir, "selfreport")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--test_all_accounts',
        '-t',
        action='store_true',
        help='测试所有账号')
    parser.add_argument(
        '--test_single_account',
        '-s',
        type=str,
        help='测试单个账号')
    parser.add_argument(
        '--test_send_email',
        '-e',
        type=str,
        help='测试邮件发送模块，后接测试测试邮件收件邮箱')
    args = parser.parse_args()

    if args.test_all_accounts:
        self_report.test_all_accounts()

    if args.test_single_account:
        self_report.test_single_account(args.test_single_account)

    if args.test_send_email:
        self_report.test_send_email(args.test_send_email)

    if args.test_all_accounts or args.test_single_account or args.test_send_email:
        exit(0)

    self_report.auto_report()
