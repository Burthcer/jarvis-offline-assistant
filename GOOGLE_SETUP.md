# Connecting Gmail and Google Calendar

Jarvis now has an optional Google connection in Settings. It reads unread Gmail subjects/senders and the next seven days of your primary Google Calendar. It cannot send, delete or change anything through this connection. Nothing syncs automatically.

One external prerequisite remains: Google requires this installed app to have a registered **Desktop OAuth client**. This project does not contain a registered Google client. A Gmail address alone cannot replace it, and Codex's account connections cannot be transferred to Jarvis.

Once the Desktop client JSON exists:
1. Open Jarvis → Settings → Google connections → Connect Google.
2. Choose the downloaded Desktop client JSON.
3. Complete Google's sign-in and read-permission consent in your browser.
4. Return to Jarvis and click Refresh status. Then try Unread Gmail or Upcoming calendar.

If a Google Cloud project is being configured, enable the Gmail API and Google Calendar API, create a Desktop OAuth client, configure its consent screen/test users as required by Google, and download the client JSON. No billing or cloud project has been created by this coding session. Do not paste your password or account tokens into Jarvis or this chat.

Refresh credentials are stored in Windows Credential Manager under `JarvisOfflineAssistant/GoogleReadOnly`. Access tokens are kept in memory. Backups exclude both. Disconnect removes the local credentials; Google account access can also be revoked in your Google account settings.

The implementation was checked against mocked Google responses and a local OAuth callback, not your actual account. Real account connection is pending the external client registration and your sign-in.

Official references: [Google desktop sign-in](https://developers.google.com/identity/protocols/oauth2/native-app), [Gmail read API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list), [Calendar permissions](https://developers.google.com/workspace/calendar/api/auth).
