# 上海大学在校生每日两报自动打卡

程序为python脚本文件，修改配置文件相关信息，设置后台运行脚本，脚本会根据配置文件信息自动进行每日两报。

本程序基于Github的[BlueFisher](https://github.com/BlueFisher/SHU-selfreport)的原始代码进行重构和增加功能而成的，我也是早期该仓库的提交者之一，这是沿用我之前提交的代码不断发展而来的。

## 环境要求

- `python3`
  - 库：`pyyaml`、`beautifulsoup4`、`requests`

## 功能

- 可在`setting_config.yaml`自定义打卡时间、报送体温、是否进行邮件提醒。

  > 注：由于本人太懒了，懒得写，所以晚报时间的设置必须大于等于18点。

- 程序运行中修改`setting_config.yaml`可以在每天的0:0生效。

- 程序运行中修改`person_config.yaml`可以在下一次提交时生效。

- 邮件smtp服务器使用SSL协议端口号，可以适应阿里云服务器等默认关闭25端口的服务器。

- 日志功能，保存30天的日志。

- 管理员功能，开启可将每日日志发送到指定邮箱。

## 用法
1. 修改 `setting_config.yaml`

   - **不需要涉及邮件发送的功能**，即不需要发送每日一报是否成功的提醒邮件和不需要管理员功能，将`report`中的`send_email`和`manager`中的`send_email`设置为`false`既可，email部分保持原样即可。

     ```yaml
     report:
       send_email: false                       # 是否发送每日一报是否成功的提醒邮件
     
       morning_hour: 7                      # 早上填报的时间
       morning_minute: 15
     
       night_hour: 20                          # 晚上填报的时间
       night_minute: 45
     
       temperature: 36.5                   # 温度，程序填报时会自动上下浮动正负0.2温度，
     
     
     // 管理员功能设置
     manager:
       send_email: false                                           # 是否发送每天的日志给程序管理员
       email_to: "xxx@xxx.xxx"                            # 接收日志的邮箱账号
       hour: 22                                                            # 发送日志的时间
       minute: 30
     
     
     // 发送邮件设置，程序将使用下面填写的邮箱服务器发送每日两报是否成功的邮件给对方
     email:
       from: "xxx@xxx.xxx"                         # 用于发送邮件的账号
       username: "xxx@xxx.xxx"              # 同上
       password: "xxx"                                  # 邮件服务器的密钥
       smtp: "smtp.xxx.xxx"                       # smtp服务器
       port: 465                                                # smtp服务器端口
     ```

   - **开启发送每日一报是否成功邮件和管理员功能中的任何一个，都需要设置`email`部分**：

     SMTP服务器，以163邮箱为例。

     ![image-20201126153117803](https://gitee.com/zhangrui_wolf/shu_selfreport/raw/master/img/img_01.png)

     ![image-20201126160517130](https://gitee.com/zhangrui_wolf/shu_selfreport/raw/master/img/img_02.png)

2. 修改`person_config.yaml`，

   注意不要省略`""`

   - `id`：学号，如`"12345678"`。
   - `pwd`：密码，如`"12345678"`。
   - `email_to`：该用户用于接收每日一报是否成功的邮件的邮箱，如果`setting_config.yaml` `report`中的`send_email`设置为`false`，可以不用填写。

   - `campus`：校区，可填`"宝山"`、`"延长"`、`"嘉定"`、`"新闸路"`或者`"不在校"`。
   - `county`：当天所在县区，建议与校区所在区相同，即建议为：`"宝山区"`、`"静安区"`、`"嘉定区"`。
   - `address`：具体地址，随便，建议填写校区地址或者宿舍地址。

   ```yaml
   - id: "xxxxxxxx"                                          # 学号
     pwd: "xxxxxxxx"                                         # 密码
     email_to: "xxxxxxxx@xxxx.xxx"                           # 邮箱
     campus: "宝山"                                           # 校区，内容可为：“宝山”，“延长”，“嘉定”
     county: "宝山区"                                         # 当天所在县区，建议与校区相同，即可为："宝山区"、"静安区"、"嘉定区"
     address: "上海市宝山区大场镇上大路99号上海大学宝山校区"       # 具体地址，随便，建议填写校区地址
   - id: "xxxxxxxx"
     pwd: "xxxxxxxx"
     email_to: "xxxxxxxx@xxxx.xxx"
     campus: "xxx"
     county: "xxx"
     address: "xxx"
   
   ```

3. 测试（可选）

   - 测试填写的所有账号密码是否正确：

     ```python
     python main.py -t
     ```
     
   - 测试`person_config.yaml`中的单个账号是否正确：

     ```python
     python main.py -s 学号
     ```

   - 测试邮箱服务是否可使用：

     ```python
     python main.py -e xxx@xx.xx        # xxx@xx.com为接收测试邮件的账号
     ```

4. 启动程序

   ```python
   # 针对启动后不关的Linux服务器，如阿里云服务器，启动程序，后台运行，当日日志输出结果导出selfreport中，往日日志会出现在selfreport.xxxx-xx-xxlog中。
   # 如使用个人电脑设置开机自启动，请自行搜索网上教程
   nohup python main.py &
   ```

## 更新日志

- 2020.11.26：程序自动生成`F_STATE`。
- 2020.11.22：适配11月22日每日两报系统的更新。