# energy-eagle-indigo-plugin
(A plugin for Indigo Domotics Indigo Pro 7 or later)

Version 0.6.1

## Introduction
This plugin enables communication with the Rainforest Energy Eagle 200 (RFA-Z114).  The plugin was written solely for the Eagle 200 and as such, compatibility with the Energy Eagle 100 is unlikely / unknown.  This plugin is inspired by the work of Nathan Sheldon who created the now deprecated plugin for the original Energy Eagle 100.  

The Energy Eagle 200 API provides fewer data points than the API on the Energy Eagle 100.  For example, summation data is no longer available from the local API. This is the initial version of the plugin and only gathers Instantaneous Demand and basic pricing data from the local API.  Time of use pricing is not currently supported.

## Requirements
This plug-in requires the python lxml library.  To install lxml on your mac, follow these steps:

1) 'sudo easy_install pip'
2) 'pip install lxml'

You may need to install Xcode (available for free from the app store) for the above commands to work.

If you have previously installed lxml and the package reports it can't be found, you may need to create a symlink that Indigo can follow.
sudo ln -s /usr/local/lib/python2.7/site-packages/lxml /Library/Python/2.7/site-packages/lxml

## Installation
Download the Energy Eagle zip file to the computer running the Indigo server. If the file is not already unzipped, double-click the .zip file to unzip it. Double-click the Energy Eagle.indigoPlugin file. The Indigo client will open and prompt to install the plugin. Click the option to install and enable the plugin.

## Usage
To add a new Eagle 200 device, simply create a new device and select type Energy Eagle.  The plugin will ask for three pieces of information: 1) the IP Address of the Energy Eagle, 2) the CloudID and 3) the Installer ID.  Items 2 & 3 are found on the bottom of the Energy Eagle unit.  The plugin will then connect the Eagle, gather the Hardware Address of the electric meter and begin collecting data from the Eagle.  These data can then be consumed via other plugins, i.e. graphing via INDIGOplotD, etc.

## To Do
1) Automatic plugin update checking
