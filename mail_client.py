#!/usr/bin/env python3
"""Simple command-line email client using SMTP and IMAP.

Features:
- send email via SMTP
- list recent inbox messages via IMAP
- read message details and body
- send emails with file attachments
- save attachments from received messages
- optionally mark messages as deleted

Example config file (~/.mail_program_config.json):
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 465,
  "imap_host": "imap.gmail.com",
  "imap_port": 993,
  "username": "you@gmail.com",
  "password": "your-app-password",
  "from_email": "you@gmail.com"
}
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from typing import Any, Dict, List

try:
    import imaplib
    import smtplib
except Exception as exc:  # pragma: no guard
    print(f"Failed to import email libraries: {exc}", file=sys.stderr)
    raise

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.mail_program_config.json")


def load_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config file not found: {path}. Create it with sample values or use --config."
        )

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    required = [
        "smtp_host",
        "smtp_port",
        "imap_host",
        "imap_port",
        "username",
        "password",
        "from_email",
    ]
    missing = [key for key in required if key not in data or not data[key]]
    if missing:
        raise ValueError(f"Missing required config fields: {', '.join(missing)}")
    return data


def save_sample_config(path: str) -> None:
    sample = {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "username": "your-email@example.com",
        "password": "your-app-password",
        "from_email": "your-email@example.com",
    }
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sample, fh, indent=2)
        fh.write("\n")
    print(f"Sample config written to {path}")


def build_message(from_email: str, to: str, subject: str, body: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = from_email
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return message


def build_message_with_attachment(from_email: str, to: str, subject: str, body: str, attachment_path: str) -> EmailMessage:
    if not os.path.exists(attachment_path):
        raise FileNotFoundError(f"Attachment not found: {attachment_path}")

    message = EmailMessage()
    message["From"] = from_email
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    mime_type, _ = mimetypes.guess_type(attachment_path)
    if mime_type is None:
        mime_type = "application/octet-stream"

    maintype, subtype = mime_type.split("/", 1)
    filename = os.path.basename(attachment_path)

    with open(attachment_path, "rb") as file_handle:
        message.add_attachment(
            file_handle.read(),
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )

    return message


def send_email(config: Dict[str, Any], to: str, subject: str, body: str) -> None:
    message = build_message(config["from_email"], to, subject, body)

    with smtplib.SMTP_SSL(config["smtp_host"], int(config["smtp_port"])) as smtp:
        smtp.login(config["username"], config["password"])
        smtp.send_message(message)

    print(f"Email sent to {to}")


def send_email_with_attachment(config: Dict[str, Any], to: str, subject: str, body: str, attachment_path: str) -> None:
    message = build_message_with_attachment(config["from_email"], to, subject, body, attachment_path)

    with smtplib.SMTP_SSL(config["smtp_host"], int(config["smtp_port"])) as smtp:
        smtp.login(config["username"], config["password"])
        smtp.send_message(message)

    print(f"Email with attachment sent to {to}")


def parse_email_message(raw_message: bytes):
    return BytesParser(policy=policy.default).parsebytes(raw_message)


def iter_inbox_messages(config: Dict[str, Any], folder: str = "INBOX", limit: int = 10, unread_only: bool = False):
    with imaplib.IMAP4_SSL(config["imap_host"], int(config["imap_port"])) as imap:
        imap.login(config["username"], config["password"])
        imap.select(folder)

        search_criteria = "UNSEEN" if unread_only else "ALL"
        status, message_ids = imap.search(None, search_criteria)
        if status != "OK":
            raise RuntimeError(f"IMAP search failed: {message_ids}")

        ids = message_ids[0].decode("utf-8").split()
        if not ids:
            print("No messages found.")
            return []

        selected_ids = ids[-limit:]
        messages = []
        for msg_id in selected_ids:
            status, data = imap.fetch(msg_id.encode("utf-8"), "(RFC822)")
            if status != "OK":
                continue
            raw = data[0][1]
            messages.append(parse_email_message(raw))
        return messages


def message_summary(message) -> Dict[str, Any]:
    subject = message.get("Subject", "") or "(no subject)"
    sender = message.get("From", "") or "unknown sender"
    date = message.get("Date", "") or "unknown date"
    return {"subject": subject, "from": sender, "date": date}


def get_message_body(message) -> str:
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""

    payload = message.get_payload(decode=True)
    if payload is None:
        return ""

    charset = message.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def get_message_attachments(message) -> List[Any]:
    attachments = []

    if message.is_multipart():
        for part in message.walk():
            filename = part.get_filename()
            if filename:
                attachments.append(part)
    else:
        if message.get_filename() or message.get_content_disposition() == "attachment":
            attachments.append(message)

    return attachments


def save_attachments(message, output_dir: str) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    saved_files = []

    for part in get_message_attachments(message):
        filename = part.get_filename() or "attachment.bin"
        target_name = os.path.basename(filename)
        target_path = os.path.join(output_dir, target_name)

        counter = 1
        while os.path.exists(target_path):
            base, ext = os.path.splitext(target_name)
            target_path = os.path.join(output_dir, f"{base}_{counter}{ext}")
            counter += 1

        payload = part.get_payload(decode=True)
        if payload is None:
            payload = part.get_content().encode("utf-8", errors="replace") if isinstance(part.get_content(), str) else b""

        with open(target_path, "wb") as file_handle:
            file_handle.write(payload)

        saved_files.append(target_path)

    return saved_files


def print_message_list(messages: List[Any]) -> None:
    if not messages:
        print("No messages found.")
        return

    for index, message in enumerate(messages, start=1):
        summary = message_summary(message)
        attachments = get_message_attachments(message)
        attachment_suffix = " [attachment]" if attachments else ""
        print(f"{index}. {summary['subject']} | {summary['from']} | {summary['date']}{attachment_suffix}")


def print_message_details(message) -> None:
    print(f"From: {message.get('From', 'unknown')}")
    print(f"To: {message.get('To', 'unknown')}")
    print(f"Subject: {message.get('Subject', '(no subject)')}")
    print(f"Date: {message.get('Date', 'unknown')}")

    attachments = get_message_attachments(message)
    if attachments:
        print("Attachments:")
        for part in attachments:
            print(f" - {part.get_filename() or 'unnamed attachment'}")

    print("-" * 60)
    body = get_message_body(message)
    print(body.strip() if body.strip() else "(no message body)")


def read_message_with_attachments(config: Dict[str, Any], index: int, folder: str = "INBOX", limit: int = 10, unread_only: bool = False, output_dir: str = "downloaded_attachments") -> None:
    messages = iter_inbox_messages(config, folder=folder, limit=limit, unread_only=unread_only)
    if index < 1 or index > len(messages):
        print(f"Invalid message index. Available messages: {len(messages)}")
        return

    message = messages[index - 1]
    print_message_details(message)

    saved = save_attachments(message, output_dir)
    if saved:
        print("\nSaved attachments:")
        for path in saved:
            print(f" - {path}")
    else:
        print("\nNo attachments found.")


def delete_message(config: Dict[str, Any], message_id: str, folder: str = "INBOX") -> None:
    with imaplib.IMAP4_SSL(config["imap_host"], int(config["imap_port"])) as imap:
        imap.login(config["username"], config["password"])
        imap.select(folder)
        imap.store(message_id.encode("utf-8"), "+FLAGS", "(\\Deleted)")
        imap.expunge()
        print(f"Message {message_id} marked deleted and expunged.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simple CLI email client")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to JSON config file (default: ~/.mail_program_config.json)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # send
    send_parser = subparsers.add_parser("send", help="Send an email")
    send_parser.add_argument("to", help="Recipient email address")
    send_parser.add_argument("subject", help="Email subject")
    send_parser.add_argument("body", help="Email body text")

    # send attachment
    send_attachment_parser = subparsers.add_parser("send-attachment", help="Send an email with a file attachment")
    send_attachment_parser.add_argument("to", help="Recipient email address")
    send_attachment_parser.add_argument("subject", help="Email subject")
    send_attachment_parser.add_argument("body", help="Email body text")
    send_attachment_parser.add_argument("attachment", help="Path to attachment file")

    # list
    list_parser = subparsers.add_parser("list", help="List inbox messages")
    list_parser.add_argument("--limit", type=int, default=10, help="Maximum number of messages to display")
    list_parser.add_argument("--unread-only", action="store_true", help="Only show unread messages")
    list_parser.add_argument("--folder", default="INBOX", help="Mailbox folder to read from")

    # read
    read_parser = subparsers.add_parser("read", help="Read a message by index from the current inbox list")
    read_parser.add_argument("index", type=int, help="Message index shown by list command")
    read_parser.add_argument("--limit", type=int, default=10, help="Maximum number of messages to inspect")
    read_parser.add_argument("--unread-only", action="store_true", help="Only consider unread messages")
    read_parser.add_argument("--folder", default="INBOX", help="Mailbox folder to read from")

    # read attachments
    read_attachments_parser = subparsers.add_parser("read-attachments", help="Read a message and save any attachments")
    read_attachments_parser.add_argument("index", type=int, help="Message index shown by list command")
    read_attachments_parser.add_argument("--limit", type=int, default=10, help="Maximum number of messages to inspect")
    read_attachments_parser.add_argument("--unread-only", action="store_true", help="Only consider unread messages")
    read_attachments_parser.add_argument("--folder", default="INBOX", help="Mailbox folder to read from")
    read_attachments_parser.add_argument("--output-dir", default="downloaded_attachments", help="Directory to save attachments to")

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete a message by IMAP message ID")
    delete_parser.add_argument("message_id", help="IMAP message ID, such as 123")
    delete_parser.add_argument("--folder", default="INBOX", help="Mailbox folder")

    # init-config
    init_parser = subparsers.add_parser("init-config", help="Create a sample config file")
    init_parser.add_argument("--path", default=DEFAULT_CONFIG_PATH, help="Where to save the config file")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-config":
        save_sample_config(args.path)
        return 0

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        print("Tip: run 'mail_client.py init-config' to generate a sample config file.", file=sys.stderr)
        return 1

    try:
        if args.command == "send":
            send_email(config, args.to, args.subject, args.body)
        elif args.command == "send-attachment":
            send_email_with_attachment(config, args.to, args.subject, args.body, args.attachment)
        elif args.command == "list":
            messages = iter_inbox_messages(config, folder=args.folder, limit=args.limit, unread_only=args.unread_only)
            print_message_list(messages)
        elif args.command == "read":
            messages = iter_inbox_messages(config, folder=args.folder, limit=args.limit, unread_only=args.unread_only)
            if args.index < 1 or args.index > len(messages):
                print(f"Invalid message index. Available messages: {len(messages)}")
                return 1
            print_message_details(messages[args.index - 1])
        elif args.command == "read-attachments":
            read_message_with_attachments(
                config,
                args.index,
                folder=args.folder,
                limit=args.limit,
                unread_only=args.unread_only,
                output_dir=args.output_dir,
            )
        elif args.command == "delete":
            delete_message(config, args.message_id, folder=args.folder)
        else:
            parser.error(f"Unsupported command: {args.command}")
    except Exception as exc:  # pragma: no cover
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
