import os
import time
import subprocess
import glob
import string
from ctypes import windll

log_dir = 'usb_logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

current_date = time.strftime('%d.%m.%Y')
log_file_name = f'{current_date}.txt'
log_file_path = os.path.join(log_dir, log_file_name)

# GetDriveType constants
DRIVE_REMOVABLE = 2


def convert_size(size_in_bytes):
    # Convert the size to MB, GB, or KB based on its value
    if size_in_bytes >= 1e9:  # Greater than or equal to 1 GB
        return f"{size_in_bytes / 1e9:.2f} GB"
    elif size_in_bytes >= 1e6:  # Greater than or equal to 1 MB
        return f"{size_in_bytes / 1e6:.2f} MB"
    elif size_in_bytes >= 1e3:  # Greater than or equal to 1 KB
        return f"{size_in_bytes / 1e3:.2f} KB"
    else:
        return f"{size_in_bytes} bytes"


def monitor_usb():
    initial_devices = get_connected_devices()
    logged_devices = set()
    last_processed_timestamp = None

    while True:
        time.sleep(1)  # Wait for 1 second before checking again

        current_devices = get_connected_devices()

        new_devices = list(set(current_devices) - set(initial_devices))
        removed_devices = list(set(initial_devices) - set(current_devices))

        # Log inserted devices
        for device in new_devices:
            if device not in logged_devices:
                log_device_event(device, '', 'USB DEVICE INSERTED')
                logged_devices.add(device)

        # Log removed devices
        for device in removed_devices:
            if device in logged_devices:
                log_device_event(device, '', 'USB DEVICE REMOVED')
                logged_devices.remove(device)

        initial_devices = current_devices

        # Get the list of available USB drives
        usb_drives = get_usb_drive_path()

        for usb_drive_path in usb_drives:
            # Get the list of files in the USB drive
            files = glob.glob(os.path.join(usb_drive_path, '*'))

            # Filter files based on the last processed timestamp
            if last_processed_timestamp:
                files = [file for file in files if os.path.getctime(file) > last_processed_timestamp]

            if files:
                # Process the new files
                for file_path in files:
                    if os.path.isdir(file_path):  # Check if the item is a folder
                        folder_name = os.path.basename(file_path)
                        num_files, num_folders = count_files_and_folders_in_folder(file_path)
                        list_and_log_files_in_folder(file_path, folder_name, num_files, num_folders)
                    else:
                        drive_name = os.path.splitdrive(usb_drive_path)[0]
                        file_name = os.path.basename(file_path)
                        file_size = os.path.getsize(file_path)  # Get the file size in bytes
                        size_formatted = convert_size(file_size)

                        log_message = f"Copied file name: {file_name} -----> Destination drive: {drive_name} (Size: {size_formatted})"
                        log_device_event(drive_name, file_name, '', file_path=file_path)  # Log the file copying event

                        print(log_message)

                # Update the last processed timestamp
                last_processed_timestamp = max(os.path.getctime(file) for file in files)


def count_files_and_folders_in_folder(folder_path):
    num_files = 0
    num_folders = 0
    for _, _, files in os.walk(folder_path):
        num_files += len(files)
        num_folders += 1
    return num_files, num_folders


def list_and_log_files_in_folder(folder_path, folder_name, num_files, num_folders):
    folder_files = list_files_in_folder(folder_path)
    drive_name = os.path.splitdrive(folder_path)[0]
    folder_size = sum(os.path.getsize(file) for file in folder_files)

    log_message = f"Copied Main folder name: {folder_name} " \
                  f"-----> Destination drive: {drive_name} (Size: {convert_size(folder_size)})\n\n"

    # Log subfolders
    subfolder_list = []
    for root, dirs, _ in os.walk(folder_path):
        for subfolder in dirs:
            subfolder_list.append(subfolder)

    if subfolder_list:
        log_message += "Number of subfolders: {}\n".format(len(subfolder_list))
        log_message += "\n".join(f"{idx}: {subfolder}" for idx, subfolder in enumerate(subfolder_list, start=1)) + "\n\n"

    # Log files
    file_list = []
    for idx, folder_file in enumerate(folder_files, start=1):
        file_name = os.path.relpath(folder_file, folder_path)
        file_extension = os.path.splitext(file_name)[1].lower()

        # Skip logging if the file has ".ini" extension
        if file_extension == ".ini":
            continue

        file_size = os.path.getsize(folder_file)
        size_formatted = convert_size(file_size)

        file_list.append(f"{idx}: {file_name} -----> Destination drive: {drive_name} (Size: {size_formatted})")

    if file_list:
        log_message += "Number of files in folder: {}\n".format(len(file_list))
        log_message += "\n".join(file_list) + "\n\n"

    with open(log_file_path, 'a') as f:
        f.write(log_message)



def list_files_in_folder(folder_path):
    folder_files = []
    for root, _, files in os.walk(folder_path):
        folder_files.extend([os.path.join(root, file) for file in files])
    return folder_files


def get_connected_devices():
    devices = []
    cmd = 'wmic path Win32_PnPEntity WHERE "DeviceID LIKE \'USB%\'" get DeviceID,Name,Caption /format:list'

    output = subprocess.check_output(cmd, shell=True, universal_newlines=True)

    lines = output.strip().split('\n')
    device_info = [line.split('=')[1].strip() for line in lines if line.startswith(('DeviceID', 'Name', 'Caption'))]

    # Split the device_info into groups of DeviceID, Name, and Caption
    for i in range(0, len(device_info), 3):
        devices.append((device_info[i], device_info[i + 1], device_info[i + 2]))

    return devices


def log_device_event(drive_name, file_name, event, file_path=''):
    log_file = log_file_path

    with open(log_file, 'a') as f:
        current_time_formatted = time.strftime('%Y-%m-%d %H:%M:%S')

        if event.startswith('USB DEVICE'):
            device_info = f'\n Event: {event}\n\n' \
                          f'Date/Time: {current_time_formatted}\n' \
                          f'Username/Domain: {os.getlogin()}\n' \
                          f'Device Drive: {drive_name[0]}\n' \
                          f'Device ID: {drive_name[1]}\n' \
                          f'Device Type: {drive_name[2]}\n\n'
            f.write(device_info)

        elif event.startswith('FILE COPIED') and file_path and os.path.isdir(file_path):
            folder_name = os.path.basename(file_path)
            folder_size = sum(os.path.getsize(file) for file in list_files_in_folder(file_path))
            folder_size_formatted = convert_size(folder_size)

            num_files, num_folders = count_files_and_folders_in_folder(file_path)
            log_message = f'Event: FILE COPIED\n\n' \
                          f'Copied folder name: {folder_name} -----> Destination drive: {drive_name} (Size: {folder_size_formatted})\n' \
                          f'Number of files in folder: {num_files}\n' \
                          f'Number of subfolders: {num_folders - 1}\n'

            f.write(log_message)

            for idx, folder_file in enumerate(list_files_in_folder(file_path), start=1):
                file_name = os.path.basename(folder_file)
                log_message = f"File name {idx}: {file_name}\n"

                file_size = os.path.getsize(folder_file)
                size_formatted = convert_size(file_size)
                log_message += f"Copied file name: {file_name} -----> Destination drive: {drive_name} (Size: {size_formatted})\n"
                f.write(log_message)

        else:
            size_in_bytes = os.path.getsize(file_path) if file_path else 0
            size_formatted = convert_size(size_in_bytes)

            device_info = f'Event: FILE COPIED\n\n' \
                          f"Copied file name: {file_name} -----> Destination drive: {drive_name} (Size: {size_formatted})\n\n"
            f.write(device_info)


def get_usb_drive_path():
    drives = []
    for letter in string.ascii_uppercase:
        drive_path = letter + ':\\'
        if os.path.exists(drive_path) and os.path.isdir(drive_path):
            drive_type = windll.kernel32.GetDriveTypeW(drive_path)
            if drive_type == DRIVE_REMOVABLE:
                drives.append(drive_path)
    return drives


if __name__ == '__main__':
    monitor_usb()