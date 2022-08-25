#!/bin/bash

CURRENT=$(dirname "$0")

DEB=$CURRENT/wlan-manager-deb

set -e

#
# function to update the version code of .deb package
#
update_version() {

	# get the version code from .deb package
	DEB_FILE=$DEB/DEBIAN/control

	if [ ! -f $DEB_FILE ]; then
		echo
		echo "Error: $DEB_FILE not available"
		exit 2;
	fi

	DEB_VERSION=$(grep -P -i '^.*(\d(\.\d)+).*[0-9]+$' $DEB_FILE | awk '{print $2}' | cut -d"-" -f1)
	DEB_BUILDS=$(grep -P -i '^.*(\d(\.\d)+).*[0-9]+$' $DEB_FILE | awk -F '[-]' '{print $2}')

	if [ -z $DEB_VERSION ]; then
		echo
		echo "Error: Fail to gather the .deb version"
		exit 2;
	fi

	if [ -z $DEB_BUILDS ]; then
		echo
		echo "Error: Fail to gather the .deb builds"
		exit 2;
	fi

	# DEB_BUILDS_NEW=$(expr $DEB_BUILDS + 1)
        DEB_BUILDS_NEW=$(expr $DEB_BUILDS)

	OLD=$DEB_VERSION-$DEB_BUILDS
	NEW=$DEB_VERSION-$DEB_BUILDS_NEW

	echo
	echo "Version update from $OLD to $NEW"
	echo

	sed -i -e "s/$OLD/$NEW/g" $DEB_FILE

}

# update the version code
update_version

# generate debian(.deb) package
dpkg -b $DEB .

TARGET_FILE=$(find . -type f -name "wlan-manager*.deb")

PACKAGE=$(echo $TARGET_FILE | cut -d "_" -f 1)
VERSION=$(echo $TARGET_FILE | cut -d "_" -f 2)

echo "Rename package ($TARGET_FILE) to $PACKAGE-$VERSION"
mv $TARGET_FILE $PACKAGE-$VERSION.deb
