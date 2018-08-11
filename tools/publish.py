#!/usr/bin/env python3

import argparse
import discord
import requests
import yaml
import subprocess, os, sys, shutil

if "CYGWIN" in platform.system():
	def cygpath(path, type="u"):
		binPath = subprocess.check_output(["cygpath", "-w", path])
		return(binPath.decode("UTF-8")[:-1])

class Project:
	def __init__(self, name):
		self.name = name
		self.localRepository = None
		self.gitHubRepository = None
		self.discordWebhook = None
		self.steamPublisher = None
	
	def setLocalRepository(self, *args, **kwargs):
		self.localRepository = LocalRepository(*args, **kwargs)
	
	def setGitHubRepository(self, *args, **kwargs):
		self.gitHubRepository = GitHubRepository(*args, **kwargs)
	
	def setDiscordWebhook(self, *args, **kwargs):
		self.discordWebhook = DiscordWebhook(*args, **kwargs)
	
	def setSteamPublisher(self, *args, **kwargs):
		self.steamPublisher = SteamPublisher(*args, **kwargs)
	
	def publish(self, tag):
		if not self.localRepository:
			raise ValueError("No local repository was not yet set.\nCall <project>.setLocalRepository first.")
		folder, zip_file = self.localRepository.pack()
		if self.gitHubRepository:
			release = self.gitHubRepository.createRelease(tag)
			release.uploadAsset(zip_file)
		if self.discordWebhook:
			self.discordWebhook.run()
		if self.steamPublisher:
			if "CYGWIN" in platform.system():
				folder = cygpath(folder, "w")
			self.steamPublisher.run(folder)

class LocalRepository:
	def __init__(self, source="", target="", zip="", sourceBikey="", targetBikey="", ignore=()):
		self.source = source
		self.target = target
		self.zip = zip
		self.sourceBikey = sourceBikey
		self.targetBikey = targetBikey
		self.ignore = ignore
	def pack():
		# Clear target folder
		if os.path.exists(target):
			shutil.rmtree(target)
		# Copy project to release folder
		# filter for ignored files/folders
		def ignore(path, contents):
			# ignore private key folder
			if "private" in contents:
				ignored = ["private"]
			# ignore addon source folders
			elif "addons" in path[-6:]:
				ignored = list(filter(lambda content: os.path.isdir(os.path.join(path, content)), contents))
			else:
				ignored = []
			return ignored
		shutil.copytree(self.source, self.target, ignore=ignore)
		# copy bikey
		shutil.copyfile(self.sourceBikey, self.targetBikey)
		
		# Pack release
		shutil.make_archive(self.zip[:-4], "zip", os.path.dirname(self.target), os.path.basename(self.target))
		return (self.target, self.zip)

class GitHubRepository:
	def __init__(self, user="", project="", token="", changelog=""):
		self.token = token
		self.user = user
		self.project = project
		self.base_api_url = "https://api.github.com/repos/{}/{}".format(user, project)
		self.base_upload_url = "https://uploads.github.com/repos/{}/{}".format(user, project)
		self.changelog = changelog
		self.releases = {}
	
	def createRelease(self, tag, title="", **kwargs):
		if not title:
			title = "{} {}".format(self.project, tag)
		release = Release(tag=tag, title=title, _repo=self, **kwargs)
		self.releases[tag] = release
		return(release)
		
	class Release:
		def __init__(self, id="", tag="", target="master", title="", changelog="", draft=False, prerelease=False, _repo=None):
			self._repo = _repo
			self.id = id
			self.tag = tag
			self.target = target
			self.title = title
			self.changelog = changelog
			self.isDraft = draft
			self.isPrerelease = prerelease
		
		def publish(self):
			url = "{0.base_api_url}/releases?access_token={0.token}".format(self._repo)
			body = {
				"tag_name": self.tag,
				"target_commitish": self.target,
				"name": self.title,
				"body": self.changelog,
				"draft": self.isDraft,
				"prerelease": self.isPrerelease
			}
			response = requests.post(url, json=body)
			response.raise_for_status()
			self.id = response.json()["id"]
			return(response)
		
		def uploadAsset(self, file, content_type="application/zip"):
			url = "{0.base_upload_url}/releases/{1.id}/assets?name={2}&access_token={0.token}".format(self._repo, self, os.path.basename(file))
			headers = {"Content-Type": content_type}
			body = open(file,"rb").read()
			response = requests.post(url, headers=headers, data=body)
			response.raise_for_status()
			return(response)

class SteamPublisher:
	def __init__(self, id=-1, message="", **kwargs):
		self.id = id
		self.message = message
	def run(self, folder, message=""):
		if not message:
			message = self.message
		cmd_line = [SteamPublisherCMD, "update"]
		cmd_line.append("/id:{}".format(self.id))
		cmd_line.append("/changeNote:{}".format(message))
		cmd_line.append("/path:{}".format(folder))
		subprocess.check_output(cmd_line, stdout=sys.stdout, stderr=sys.stderr)

class DiscordWebhook:
	def __init__(self, message="", **kwargs):
		self.url = url
	def run(self, message=""):
		if not message:
			message = self.message
		body = {
			"content": message
		}
		response = requests.post(self.url, data=body)
		response.raise_for_status()
		return(response)

if __name__ == "__main__":
	project_name, release_tag = ("Achilles", "v1.1.2")
	config = yaml.load(open(__file__[:-2] + "yaml", "r"))
	common_config = config["Common"]
	if not project_name:
		project_name = common_config["DefaultProject"]
	project_config = config["Projects"][project_name]
	# Format all string config values 
	for category, dict in project_config.items():
		for key, value in dict.items():
			if isinstance(str, value): 
				project_config[category][key] = value.format(tag=release_tag, **project_config)
	# Create the project
	project = Project(project_name)
	# Initialize the different interfaces
	project.setLocalRepository(**project_config["LocalRepository"])
	project.setGitHubRepository(**project_config["GitHubRepository"])
	project.setSteamPublisher(**project_config["SteamPublisher"])
	project.setDiscordWebhook(**project_config["DiscordWebhook"])
	# Publish
	project.publish(release_tag)
