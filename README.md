# Hallenreservation

We regularly receive emails containing reservation confirmations that we want to store automatically. This small tool automates this process.

This repo can:
1. Fetch unread emails for an office 365 shared mailbox
2. find all pdf attachments
3. call OpenAI to obtain a fitting filename including a date for the reservation
4. upload the attachments to a sharepoint folder under the new filename


#ToDo: add tests ;)