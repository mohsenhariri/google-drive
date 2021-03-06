"""
DocString
https://docs.python.org/3/library/io.html
"""
import pickle
from os import getenv
from pathlib import Path
from pprint import pprint as print
from urllib.parse import urlparse

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

import mime


class Drive:
    global SCOPES
    SCOPES = [
        "https://www.googleapis.com/auth/drive.metadata.readonly",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self) -> None:
        creds = None

        path_token = Path(getenv("PATH_TOKEN"))

        if path_token.exists():
            with open(".token", "rb") as fp:
                try:
                    creds = pickle.load(fp)
                except Exception as err:
                    print(".token file exists, but it damaged.", err)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(".credentials", SCOPES)
                creds = flow.run_local_server(port=0)

            with open(".token", "wb") as fp:
                pickle.dump(creds, fp)

        try:
            self.service = build("drive", "v3", credentials=creds)
        except HttpError as err:
            print("Can not stablish the connection.", err)

    def id_parser(self, url):
        """
        type =
        drive
        file
        document, spreadsheet
        """
        # check the url is valid
        try:
            parse = urlparse(url).path.split("/")
            type = parse[1]
            id = parse[3]
            return type, id
        except Exception as err:
            print("URL is invalid.")
            exit(1)

    def sanitizer(self, name: str) -> str:
        file_name = name.replace("/", "_")  # replace illegal characters
        return file_name

    def files_folder(self, folder_id, pageSize=10):

        page_token = None
        while True:
            """
            application/vnd.google-apps.folder
            https://developers.google.com/drive/api/guides/search-files
            https://developers.google.com/drive/api/v3/reference/files/list

            """
            response = (
                self.service.files()
                .list(
                    q=f"'{folder_id}' in parents",
                    pageSize=pageSize,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, mimeType, parents)",
                    pageToken=page_token,
                )
                .execute()
            )

            items = response.get("files", [])
            page_token = response.get("nextPageToken", None)

            # print("next")

            if page_token is None:
                break

        if not items:
            print("No files found.")

        return items

    def file_metadata(self, file_id, out):
        try:
            metadata = self.service.files().get(fileId=file_id).execute()
            item = metadata
            self.download_file(item, out)
        except HttpError as error:
            print(f"An error occurred: {error}")
            print(f"An error occurred: {error.status_code}")

        except Exception as error:
            print(f"An Exception occurred: {error}")

    def download_file(self, item, path_parent):
        """ """
        file_mime = item["mimeType"]
        file_id = item["id"]
        file_name = self.sanitizer(item["name"])

        try:
            if file_mime in mime.google:
                mimeType = mime.mime_convert[file_mime]
                extension = mimeType.split("/")[1]
                file_name = f"{file_name}.{extension}"

                request = self.service.files().export(fileId=file_id, mimeType=mimeType)

            else:
                request = self.service.files().get_media(fileId=file_id)

            path_file = Path(rf"{path_parent}/{file_name}")

            if path_file.exists():
                print(f"{path_file} already exists.")

            with open(path_file, "wb") as fd:
                downloader = MediaIoBaseDownload(fd, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    print(f"{path_file} is downloading {int(status.progress() * 100)}")

        except HttpError as error:
            print(f"An error occurred: {error}")
        except Exception as error:
            print(f"An Exception occurred: {error}")

    def download(self, url, depth, out):
        """
        Download all files in parent and all sub directories
        """
        type, id = self.id_parser(url)

        def traverse(id, path_parent, depth_current):
            if depth_current > depth:
                print("finish depth")
                return

            files_and_folders = self.files_folder(id)

            for file in files_and_folders:
                mime_type = file["mimeType"]

                if mime_type == "application/vnd.google-apps.folder":

                    path_directory = Path(rf'{path_parent}/{file["name"]}')
                    path_directory.mkdir(parents=True, exist_ok=True)
                    file["inside"] = traverse(
                        id=file["id"],
                        path_parent=path_directory,
                        depth_current=depth_current + 1,
                    )
                else:
                    self.download_file(file, path_parent)

            return files_and_folders

        if type == "drive":
            return traverse(id, out, depth_current=0)
        else:
            self.file_metadata(id, out)

    def download_file_memory(self, file_id):
        """ """
        try:
            request = self.service.files().get_media(fileId=file_id)
            binary_file = request.execute()
            return binary_file

        except HttpError as error:
            print(f"An error occurred: {error}")
        except Exception as error:
            print(f"An Exception occurred: {error}")

    def download_memory(self, url):
        """ """
        _, id = self.id_parser(url)
        files_and_folders = self.files_folder(id)
        for file in files_and_folders:
            yield self.download_file_memory(file_id=file["id"])
