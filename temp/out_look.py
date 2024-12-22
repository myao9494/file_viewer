import win32com.client
import datetime

def copy_outlook_meeting(meeting_name):
    """
    Outlookの会議をコピーして、新しい会議を作成する関数。
    
    Args:
        meeting_name: コピー元の会議名 (文字列)。
    """
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
    except Exception as e:
        print(f"Outlookの初期化に失敗しました: {e}")
        return

    try:
        appointments = namespace.GetDefaultFolder(9).Items  # 9: olFolderCalendar (カレンダー)
        filter_query = f"[Subject] = '{meeting_name}' AND [Class] = 43"
        filtered_appointments = appointments.Restrict(filter_query)
        
        if len(filtered_appointments) == 0:
            print(f"会議 '{meeting_name}' が見つかりませんでした。")
            return
        
        for target_meeting in filtered_appointments:
            copy_meeting(target_meeting)
    except Exception as e:
        print(f"会議の検索中にエラーが発生しました: {e}")


def copy_meeting(target_meeting):
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        subject = target_meeting.Subject
        start_time = target_meeting.Start
        end_time = target_meeting.End
        location = target_meeting.Location
        body = target_meeting.Body
        required_attendees = [attendee.Address for attendee in target_meeting.Recipients if attendee.Type == 1]
        optional_attendees = [attendee.Address for attendee in target_meeting.Recipients if attendee.Type == 2]
        resources = [attendee.Address for attendee in target_meeting.Recipients if attendee.Type == 3]

        new_meeting = outlook.CreateItem(1)  # 1: olAppointmentItem
        new_meeting.Subject = subject
        new_meeting.Start = start_time
        new_meeting.End = end_time
        new_meeting.Location = location
        new_meeting.Body = body

        all_recipients = set(required_attendees + optional_attendees + resources)
        for address in all_recipients:
            recipient = new_meeting.Recipients.Add(address)
            if address in required_attendees:
                recipient.Type = 1
            elif address in optional_attendees:
                recipient.Type = 2
            elif address in resources:
                recipient.Type = 3

        new_meeting.Save()
        new_meeting.Display()
        print(f"会議 '{subject}' のコピーを作成しました。")

    except Exception as e:
        print(f"会議のコピー中にエラーが発生しました: {e}")


if __name__ == '__main__':
    meeting_name_to_copy = "コピーしたい会議の件名"  # ここにコピーしたい会議の件名を入力してください
    copy_outlook_meeting(meeting_name_to_copy)





import win32com.client
import datetime

def copy_outlook_meeting(meeting_name):
    """
    Outlookの会議をコピーして、新しい会議を作成する関数。

    Args:
        meeting_name: コピー元の会議名 (文字列)。
    """

    try:
        # Outlookアプリケーションの起動
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")

        # 会議アイテムの検索
        appointments = namespace.GetDefaultFolder(9).Items  # 9: olFolderCalendar (カレンダー)
        target_meeting = None
        for item in appointments:
            if item.Subject == meeting_name and item.Class == 43: # 43: olAppointment (会議)
                target_meeting = item
                break
        
        if target_meeting is None:
            print(f"会議 '{meeting_name}' が見つかりませんでした。")
            return
            
        # 会議情報の取得
        subject = target_meeting.Subject
        start_time = target_meeting.Start
        end_time = target_meeting.End
        location = target_meeting.Location
        body = target_meeting.Body
        required_attendees = [attendee.Address for attendee in target_meeting.Recipients if attendee.Type == 1]  # 1: olRequired
        optional_attendees = [attendee.Address for attendee in target_meeting.Recipients if attendee.Type == 2]  # 2: olOptional
        resources = [attendee.Address for attendee in target_meeting.Recipients if attendee.Type == 3] # 3: olResource
        
        # 新しい会議アイテムの作成
        new_meeting = outlook.CreateItem(1) # 1: olAppointmentItem
        
        # 会議情報の設定
        new_meeting.Subject = subject
        new_meeting.Start = start_time
        new_meeting.End = end_time
        new_meeting.Location = location
        new_meeting.Body = body
        
        # 宛先の追加
        for address in required_attendees:
            new_meeting.Recipients.Add(address).Type = 1
        for address in optional_attendees:
            new_meeting.Recipients.Add(address).Type = 2
        for address in resources:
            new_meeting.Recipients.Add(address).Type = 3
        
        new_meeting.Save()
        new_meeting.Display()
        
        print("新しい会議を作成し、表示しました。")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")


if __name__ == '__main__':
    meeting_name_to_copy = "コピーしたい会議の件名" # ここにコピーしたい会議の件名を入力してください
    copy_outlook_meeting(meeting_name_to_copy)