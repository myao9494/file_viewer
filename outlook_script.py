import win32com.client
from collections import Counter

def get_sent_item_recipients(limit=None):
    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    sent_items = outlook.GetDefaultFolder(5)  # 5 は送信済みアイテムフォルダを表します
    messages = sent_items.Items
    messages.Sort("[ReceivedTime]", True)  # 最新順にソート
    
    if limit:
        messages = messages[:limit]  # 最新N件のメールのみ取得
    
    recipients = []
    for message in messages:
        try:
            for recipient in message.Recipients:
                recipients.append(recipient.Address)
        except Exception as e:
            print(f"Error processing message: {e}")
    
    return recipients

def count_and_sort_recipients(recipients):
    counter = Counter(recipients)
    return counter.most_common()

def main():
    recipients = get_sent_item_recipients(limit=100)  # 必要に応じて制限を追加
    if not recipients:
        print("送信済みアイテムフォルダにメールがありません。")
        return
    
    sorted_recipients = count_and_sort_recipients(recipients)
    
    print("送信数の多い順にメールアドレスをリストアップします:")
    for address, count in sorted_recipients:
        print(f"{address}: {count}回")

if __name__ == "__main__":
    main()