import utils


meeting_url = input("Enter the meeting url (something like https://connect.university.com/xxxxxx/?sesssion=xxxxx):\n")
meeting_name = input("Enter the meeting name (just for saving):\n")

downloader = utils.Downloader(meeting_url, f"./downloads/{meeting_name}.zip")
print("Downloading...")
downloader.download()
print("Done!")
print("Unzipping...")
output_folder = downloader.unzip()
print("Done!")

print("Processing...")
converter = utils.Converter(output_folder, fps=10, debug=True)
converter.convert_meeting()
print("Done!")


# and if you want to convert a downloaded meeting:
# converter = utils.Converter("PATH/TO/UNZIPPED/FOLDER", fps=1, debug=True)
# converter.convert_meeting()
