import imaplib
import email
from os import getenv
from dotenv import load_dotenv
import re
import requests
import logging
import schedule
import time

logging.basicConfig(filename='api_log.txt', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

email_address = getenv("EMAIL_ADDRESS")
password = getenv("PASSWORD")
api_url = getenv("API_URL")


def process_emails():
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(email_address, password)
    mail.select('inbox')

    status, email_ids = mail.search(None, 'ALL')
    email_ids = email_ids[0].split()

    name_regex = re.compile(r'\*(?:Your |First )?Name\*\s*([^\r\n*]+)')
    email_regex = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
    website_regex = re.compile(r"<([^>]+)>")

    found_names = []
    found_emails = []
    found_websites = []

    processed_ids = set()
    with open(r"processed_emails.txt", "r") as file:
        processed_ids.update(line.strip() for line in file)

    if status == "OK":
        with open(r"processed_emails.txt", "a") as file:
            for eid in email_ids:
                if str(eid) not in processed_ids:
                    try:
                        status, msg_data = mail.fetch(eid, "(RFC822)")
                        msg = email.message_from_bytes(msg_data[0][1])
                        content = ""

                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                if content_type == "text/plain":
                                    message_content = part.get_payload(decode=True).decode("utf-8")
                                    content += message_content

                        content = content.strip()

                        name_match = name_regex.search(content)
                        email_match = email_regex.search(content)
                        website_match = website_regex.search(content)

                        if name_match and email_match and website_match:
                            found_names.append(name_match.group(1))
                            found_emails.append(email_match.group(0))
                            found_websites.append(website_match.group(1))

                        processed_ids.add(eid)
                        file.write(str(eid) + "\n")
                    except Exception as e:
                        logging.exception("An error occurred while processing email: %s", str(e))

    mail.logout()
    return found_names, found_emails, found_websites


def send_data():
    found_names, found_emails, found_websites = process_emails()

    if found_names and found_emails and found_websites:
        data = list(zip(found_names, found_emails, found_websites))
        try:
            response = requests.post(api_url, json=data)

            if response.status_code == 200:
                logging.info("Data sent successfully!")
                found_names.clear()
                found_emails.clear()
                found_websites.clear()
            else:
                logging.error("Failed to send data. Status code: %d", response.status_code)
                logging.error("Response content: %s", response.text)
        except Exception as e:
            logging.exception("An error occurred while sending the request: %s", str(e))


schedule.every(20).seconds.do(send_data)

while True:
    schedule.run_pending()
    time.sleep(1)
