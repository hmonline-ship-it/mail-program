# mail-program

A simple Python command-line email client that can send and read email using SMTP and IMAP.

## Features

- Send an email via SMTP
- List recent messages from your inbox
- Read message content from the inbox
- Optionally delete a message from the mailbox
- Uses a JSON configuration file for credentials and server settings

## Setup

1. Create a sample config file:

   ```bash
   python mail_client.py init-config
   ```

   This creates a file at `~/.mail_program_config.json`.

2. Edit the file and fill in your email settings.

   Example:

   ```json
   {
     "smtp_host": "smtp.gmail.com",
     "smtp_port": 465,
     "imap_host": "imap.gmail.com",
     "imap_port": 993,
     "username": "you@gmail.com",
     "password": "your-app-password",
     "from_email": "you@gmail.com"
   }
   ```

   For Gmail, use an app password instead of your normal account password.

## Usage

### Send mail

```bash
python mail_client.py --config ~/.mail_program_config.json send "friend@example.com" "Hello" "This is a test email."
```

### List recent inbox messages

```bash
python mail_client.py --config ~/.mail_program_config.json list --limit 10
```

### Read a message

```bash
python mail_client.py --config ~/.mail_program_config.json read 1 --limit 10
```

### Delete a message

```bash
python mail_client.py --config ~/.mail_program_config.json delete 12
```

## Notes

- IMAP and SMTP may require app-specific passwords or external authentication depending on your provider.
- Some providers block SMTP/IMAP access unless security settings are configured correctly.
- This is a lightweight command-line tool intended for learning and simple automation.

## License

MIT
