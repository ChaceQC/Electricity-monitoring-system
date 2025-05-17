import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

def send_email(to_email, subject, body, sender_email=r'', password=''):
    smtp_server = 'smtp.qq.com'
    smtp_port = 465

    # 构建邮件内容（显式UTF-8编码）
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')  # 处理中文标题

    # 处理发件人/收件人名称（即使名称为空也强制编码）
    msg['From'] = formataddr((Header('', 'utf-8').encode(), sender_email))
    msg['To'] = formataddr((Header('', 'utf-8').encode(), to_email))

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, [to_email], msg.as_string())
            try:
                server.quit()
            except smtplib.SMTPException as e:
                print(f"忽略的QUIT错误: {e}")
        print('邮件发送成功')
    except smtplib.SMTPException as e:
        print(f"邮件发送失败: {e}")
    except Exception as e:
        print(f"发生错误: {e}")

# 测试中文内容
if __name__ == "__main__":
    send_email(
        to_email='',
        subject='测试邮件-中文标题',
        body='这是包含中文内容的测试邮件'
    )