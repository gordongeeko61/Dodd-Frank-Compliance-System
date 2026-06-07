import os
import time
import logging
import requests
import yt_dlp
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient

logger = logging.getLogger("trade-surveillance.video-indexer")


class VideoIndexerService:
    def __init__(self):
        self.account_id = os.getenv("AZURE_VI_ACCOUNT_ID")
        self.location = os.getenv("AZURE_VI_LOCATION")
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        self.vi_name = os.getenv("AZURE_VI_NAME", "trade-surveillance-vi-001")
        self.credential = DefaultAzureCredential()

    def get_access_token(self):
        """Generates an ARM Access Token."""
        try:
            token_object = self.credential.get_token("https://management.azure.com/.default")
            return token_object.token
        except Exception as e:
            logger.error(f"Failed to get Azure ARM token: {e}")
            raise

    def get_account_token(self, arm_access_token):
        """Exchanges ARM token for Video Indexer Account Token."""
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            f"/generateAccessToken?api-version=2024-01-01"
        )
        headers = {"Authorization": f"Bearer {arm_access_token}"}
        payload = {"permissionType": "Contributor", "scope": "Account"}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"Failed to get VI Account Token: {response.text}")
        return response.json().get("accessToken")

    def download_youtube_video(self, url, output_path="temp_call_recording.mp4"):
        """Downloads a YouTube video (used for testing/demo recordings)."""
        logger.info(f"Downloading YouTube video: {url}")
        ydl_opts = {
            "format": "best",
            "outtmpl": output_path,
            "quiet": False,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            logger.info("YouTube download complete.")
            return output_path
        except Exception as e:
            raise Exception(f"YouTube download failed: {str(e)}")

    def download_from_blob(self, sas_url: str, output_path="temp_call_recording.mp4"):
        """
        Downloads an internal call recording from Azure Blob Storage using a SAS URL.
        Production path: Zoom/Bloomberg/Teams recordings land in a blob container,
        the surveillance pipeline generates a short-lived SAS URL and passes it here.
        """
        logger.info(f"Downloading call recording from Azure Blob Storage.")
        try:
            blob_client = BlobClient.from_blob_url(sas_url)
            with open(output_path, "wb") as f:
                stream = blob_client.download_blob()
                stream.readinto(f)
            logger.info(f"Blob download complete → {output_path}")
            return output_path
        except Exception as e:
            raise Exception(f"Azure Blob download failed: {str(e)}")

    def upload_video(self, video_path, video_name):
        """Uploads a local recording file to Azure Video Indexer."""
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        api_url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"
        params = {
            "accessToken": vi_token,
            "name": video_name,
            "privacy": "Private",
            "indexingPreset": "Default",
        }

        logger.info(f"Uploading {video_path} to Azure Video Indexer as '{video_name}'...")
        with open(video_path, "rb") as video_file:
            files = {"file": video_file}
            response = requests.post(api_url, params=params, files=files)

        if response.status_code != 200:
            raise Exception(f"Azure Video Indexer upload failed: {response.text}")

        return response.json().get("id")

    def wait_for_processing(self, video_id):
        """Polls Azure Video Indexer until the call is fully indexed."""
        logger.info(f"Waiting for Video Indexer to process video_id={video_id}...")
        while True:
            arm_token = self.get_access_token()
            vi_token = self.get_account_token(arm_token)

            url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos/{video_id}/Index"
            response = requests.get(url, params={"accessToken": vi_token})
            data = response.json()

            state = data.get("state")
            if state == "Processed":
                return data
            elif state == "Failed":
                raise Exception("Azure Video Indexer processing failed.")
            elif state == "Quarantined":
                raise Exception("Video quarantined by Azure (content policy violation).")

            logger.info(f"Status: {state} — polling again in 30s")
            time.sleep(30)

    def extract_data(self, vi_json):
        """
        Parses Azure Video Indexer JSON into CallSurveillanceState fields.
        Produces a speaker-attributed transcript so the surveillance agent knows
        which trader or RM said what.
        """
        # Build speaker ID → name map from Video Indexer speaker insights
        speaker_map = {}
        for v in vi_json.get("videos", []):
            for speaker in v.get("insights", {}).get("speakers", []):
                sid = speaker.get("id")
                name = speaker.get("name") or f"Speaker_{sid}"
                if sid is not None:
                    speaker_map[str(sid)] = name

        # Speaker-attributed transcript (critical for surveillance attribution)
        transcript_lines = []
        for v in vi_json.get("videos", []):
            for insight in v.get("insights", {}).get("transcript", []):
                speaker_id = str(insight.get("speakerId", "?"))
                speaker_label = speaker_map.get(speaker_id, f"Speaker_{speaker_id}")
                timestamp = ""
                instances = insight.get("instances", [])
                if instances:
                    timestamp = instances[0].get("start", "")
                text = insight.get("text", "")
                transcript_lines.append(f"[{speaker_label} @ {timestamp}]: {text}")

        # OCR from Bloomberg terminals, spreadsheets, or charts shared on screen
        ocr_lines = []
        for v in vi_json.get("videos", []):
            for insight in v.get("insights", {}).get("ocr", []):
                ocr_lines.append(insight.get("text", ""))

        # Named people and companies detected by Video Indexer
        named_entities = []
        for v in vi_json.get("videos", []):
            for person in v.get("insights", {}).get("namedPeople", []):
                named_entities.append(person.get("name", ""))
            for org in v.get("insights", {}).get("namedLocations", []):
                named_entities.append(org.get("name", ""))

        summarized = vi_json.get("summarizedInsights", {})
        duration_seconds = summarized.get("duration", {}).get("seconds")

        return {
            "transcript": "\n".join(transcript_lines),
            "ocr_text": ocr_lines,
            "call_metadata": {
                "duration_seconds": duration_seconds,
                "speaker_map": speaker_map,
                "named_entities_detected": named_entities,
                "platform": "internal" if len(speaker_map) > 0 else "unknown",
            },
        }
