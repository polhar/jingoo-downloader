#!/bin/python
import requests
import sys
import getopt
import json
import re
import time
import signal
from pathlib import Path

headers = {
	'X-Requested-With': 'XMLHttpRequest'
}

BASE_URI = 'http://www.jingoo.com'
LOGIN_URI = BASE_URI + '/index.php'
ALBUMS_URI = BASE_URI + '/javascripts/loadAlbum.php'
PHOTO_LIST_URI = BASE_URI + '/javascripts/liste_photos/liste_photos_album.php'


def start_session_and_login(user, password):
	try:
		session = requests.Session()

		data = {
			'login': user,
			'password': password,
			'action': 'login'
		}

		response = session.post(LOGIN_URI, data=data)

		response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)

		album_list_js = re.search(r'listAlbum\s*=\s*(\[(?>"[0-9]+",?)+\]);', response.text)

		if not album_list_js:
			raise ValueError("Album list not found in the response")

		album_list = json.loads(album_list_js.group(1))

		return session, album_list

	except requests.RequestException as e:
		print(f"Error during session start and login: {e}")
		sys.exit(2)
	except json.JSONDecodeError as e:
		print(f"Error decoding JSON: {e}")
		sys.exit(2)
	except ValueError as e:
		print(f"ValueError: {e}")
		sys.exit(2)


def get_album_names(session, album_list):
	try:
		data = {
			'albumDisplay': json.dumps(album_list),
			'tplAlbum': 'oneAlbumReport'
		}

		response = session.post(ALBUMS_URI, data=data, headers=headers)
		response.raise_for_status()

		json_response = response.json()

		if 'listeAlbum' not in json_response:
			raise ValueError("listeAlbum not found in the response")

		return json_response['listeAlbum']

	except requests.RequestException as e:
		print(f"Error during album names retrieval: {e}")
		sys.exit(2)
	except json.JSONDecodeError as e:
		print(f"Error decoding JSON: {e}")
		sys.exit(2)
	except ValueError as e:
		print(f"ValueError: {e}")
		sys.exit(2)


def get_album_pic_list(session, album_id):
	try:
		params = {
			'id_album': album_id,
			'_': int(time.time())
		}

		response = session.get(PHOTO_LIST_URI, params=params)
		response.raise_for_status()

		json_response = response.json()

		if 'listePhoto' not in json_response:
			raise ValueError("listePhoto not found in the response")

		return json_response['listePhoto']

	except requests.RequestException as e:
		print(f"Error during album pic list retrieval: {e}")
		sys.exit(2)
	except json.JSONDecodeError as e:
		print(f"Error decoding JSON: {e}")
		sys.exit(2)
	except ValueError as e:
		print(f"ValueError: {e}")
		sys.exit(2)


def download_photo(session, photo, save_path):
	try:
		photo_uri = f"{photo['srv_mini']}/medium/{photo['chemin']}"
		response = session.get(photo_uri)
		response.raise_for_status()

		content_type = response.headers.get('Content-Type', '').lower()

		if not content_type.startswith('image'):
			raise ValueError(f"Content-Type did not start with 'image' for photo {photo['nom']}")

		safe_photo_name = "".join(x for x in pic['nom'] if x != '/' and x != '\\')
		with open(save_path / safe_photo_name, 'wb') as file:
			file.write(response.content)

	except requests.RequestException as e:
		print(f"Error during photo download: {e}")
		sys.exit(2)
	except ValueError as e:
		print(f"ValueError: {e}")
		sys.exit(2)


def main(argv):
	user = ''
	password = ''
	albums = []
	path = ''

	help_message = f"{argv[0]} [-u, --user <user>] [-p, --password <password>] [-a, --album <albumID>] [-t, --path <outputPath>]"
	help_short_message = f"{argv[0]} -h, --help"

	def signal_handler(sig, frame):
		print("\nScript interrupted by user (Ctrl-C). Exiting gracefully.")
		sys.exit(0)

	# Set up a signal handler for Ctrl-C
	signal.signal(signal.SIGINT, signal_handler)

	try:
		opts, args = getopt.getopt(argv[1:], "hu:p:a:t:", ["help", "user=", "password=", "album=", "path="])
	except getopt.GetoptError:
		print(help_short_message)
		sys.exit(2)

	for opt, arg in opts:
		if opt in ("-h", "--help"):
			print(help_message)
			sys.exit()
		elif opt in ("-u", "--user"):
			user = arg
		elif opt in ("-p", "--password"):
			password = arg
		elif opt in ("-a", "--album"):
			albums = [{"idAlbum": arg, "nom": ""}]
		elif opt in ("-t", "--path"):
			path = arg

	if not user:
		user = input("user: ")
	if not password:
		password = input("password: ")

	try:
		session, album_list = start_session_and_login(user, password)

		albums_names = get_album_names(session, album_list)

		if not albums:
			albums = albums_names
		else:
			for album in albums_names:
				if albums[0]['idAlbum'] == album['idAlbum']:
					albums[0]['nom'] = album['nom']
					break
			else:
				print(f"{album['idAlbum']}: Album id not found")
				sys.exit(2)

		for album in albums:
			print(f"Album: {album['nom']} (ID {album['idAlbum']}):", end='')
			pic_list = get_album_pic_list(session, album['idAlbum'])
			print(f" {len(pic_list)} pics")

			try:
				album_path = Path(path) / album['nom']
				album_path.mkdir(parents=True, exist_ok=True)
			except FileNotFoundError as e:
				print(f"Failed to create directory '{album_path}' as a necessary parent directory does not exist. Error: {e}")
			except PermissionError as e:
				print(f"Failed to create directory '{album_path}' due to insufficient permissions. Error: {e}")
			except Exception as e:
				print(f"An unexpected error occurred: {e}")

			i = 0
			print("", end='', flush=True)
			for pic in pic_list:
				i += 1
				print(f"\r #{i}/{len(pic_list)}: {pic['nom']}, {pic['mediumx']}x{pic['mediumy']}, {pic['srv_mini']}/medium/{pic['chemin']}", end='', flush=True)
				download_photo(session, pic, album_path)
			print()

	except Exception as e:
		print(f"An unexpected error occurred: {e}")
		sys.exit(2)

if __name__ == "__main__":
	main(sys.argv)

