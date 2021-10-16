#!/usr/bin/env python3
# -*- coding: utf8

# reserve2osm
# Converts protected areas and recreation areas ("friområder") from Miljødirektoratet to osm format for import/update
# Usage: python reserve2osm.py [input_filename] (without .json)
# Default output filename: [input_filename].osm


import html
import json
import sys
import copy


version = "0.4.0"

split = True  # True for splitting polygons into network of realtions
debug = False


iucn_code = {
	'strictNatureReserve':			'1a',
	'wildernessArea':				'1b',
	'nationalPark':					'2',
	'naturalMonument':				'3',
	'habitatSpeciesManagementArea':	'4',
	'protectedLandscapeOrSeascape':	'5',
	'managedResourceProtectedArea':	'6',
	'ikkeVurdert':					'',
}

verneform_description = {
	'biotopvern':									'Biotopvernområde',  # BV
	'biotopvernSvalbard':							'Biotopvernområde',  # BVS, Svalbardmiljøloven
	'biotopvernVilt':								'Biotopvernområde',  # BVV, etter viltloven
	'dyrefredningsområde':							'Dyrefredningsområde', # DO
	'dyrelivsfredning':								'Dyrelivsfredning',  # D
	'geotopvernSvalbard':							'Geotopvernområde',  # GVS, Svalbardmiljøloven
	'landskapsvernområde':							'Landskapsvernområde',  # LVO
	'landskapsvernområdeBiotopvern':				'Landskapsvernområde med biotopvern',
	'landskapsvernområdeDyrelivsfredning':			'Landskapsvernområde med dyrelivsfredning',  # LVOD
	'landskapsvernområdePlantelivsfredning':		'Landskapsvernområde med plantelivsfredning',  # LVOP
	'landskapsvernområdePlanteOgDyrelivsfredning':	'Landskapsvernområde med plante- og dyrelivsfredning',  # LVOPD
#	'': 											'Landskapsvernområde med dyre- og plantelivsfredning',  # LVODP, typo?
	'marintVerneområde':							'Marint verneområde',  # NAVA, annet lovverk
#	'':												'Marint verneområde',  # MAV, naturmangfoldloven
#	'':												'Midlertidig vernet',  # MIV  
	'nasjonalpark':									'Nasjonalpark',  # NP
	'nasjonalparkSvalbard':							'Nasjonalpark',  # NPS, Svalbardmiljøloven
	'naturminne':									'Naturminne',    # NM
	'naturreservat':								'Naturreservat',  # NR
	'naturreservatJanMayen':						'Naturreservat',
	'naturreservatSvalbard':						'Naturreservat',  # NRS, Svalbardmiljøloven
	'plantefredningsområde':						'Plantefredningsområde',  # PO
	'plantelivsfredning':							'Plantelivsfredning',  # P
	'planteOgDyrefredningsområde':					'Plante- og dyrefredningsområde',  # PDO
	'planteOgDyrelivsfredning':						'Plante- og dyrelivsfredning'  # PD
}


verneplan_description = {   
	'verneplanNasjonalpark':	'Nasjonalpark',
	'verneplanVåtmark':			'Våtmark',
	'verneplanMyr':				'Myr',
	'verneplanLøvskog':			'Løvskog',
	'verneplanSjøfugl':			'Sjøfugl',
	'skogvern':					'Skog',
	'marinVerneplan':			'Marin',
	'annetVern':  				'',
	'kvartærgeologi':			'Kvartærgeologi',
	'fossiler':					'Fossiler',
	'ikkeVurdert':				''
}


# Output message

def message (line):

	sys.stdout.write (line)
	sys.stdout.flush()


# Log file

def log (text):

	if debug:
		logfile.write(text.encode('utf-8'))


# Produce a tag for OSM file

def make_osm_line (key,value):

	if value:
		encoded_key = html.escape(key)
		encoded_value = html.escape(value).strip()
		file.write ('    <tag k="%s" v="%s" />\n' % (encoded_key, encoded_value))


# Search for start and end nodes in ways

def find_node_id (coordinate):

	for way in ways:
		if ("start_node1" in way) and (coordinate[0] == way['line'][0][0]) and (coordinate[1] == way['line'][0][1]):
			return way['start_node1']
		if ("end_node1" in way) and (coordinate[0] == way['line'][-1][0]) and (coordinate[1] == way['line'][-1][1]):
			return way['end_node1']

	return None


# Search for node in nearby ways

def find_node (coordinate_query):

	global near_ways

	for way in near_ways:
		index = -1

		for coordinate in ways[way]['line']:
			index += 1

			if (coordinate[0] == coordinate_query[0]) and (coordinate[1] == coordinate_query[1]):
				log ("Found way #%i, node %i\n" % (way, index))
				return (way, index)

	return (None, None)


# Create new way dict, including bounding box

def create_way (line):

	max_lat = line[0][1]
	min_lat = line[0][1]	
	max_lon = line[0][0]
	min_lon = line[0][0]

	for coordinate in line[1:]:
		max_lat = max(max_lat, coordinate[1])
		min_lat = min(min_lat, coordinate[1])
		max_lon = max(max_lon, coordinate[0])
		min_lon = min(min_lon, coordinate[0])

	new_way = {
		'line':    line,
		'max_lat': max_lat,
		'min_lat': min_lat,
		'max_lon': max_lon,
		'min_lon': min_lon
	}

	return new_way


# Split way at given position
# Add the new segment at the end of ways list and add to nearby ways

def split_way (way_ref, split_position):

	global near_ways

	log ("Split line old: #%i, len %i, pos %i \n" % (way_ref, len(ways[way_ref]['line']), split_position))

	line1 = ways[way_ref]['line'][0:split_position + 1]
	line2 = ways[way_ref]['line'][split_position:]

	new_way = create_way(line1)
	ways[way_ref] = new_way

	new_way = create_way(line2)
	ways.append(new_way)

	near_ways.append(len(ways) - 1)

	log ("  Split line 1: #%i, len %i\n" % (way_ref, len(line1)))
	log ("  Split line 2: #%i, len %i\n" % (len(ways) - 1, len(line2)))

	for ref, area in iter(areas.items()):
		member_index = -1
		for area_member in area['members']:
			member_index += 1
			if area_member['way_ref'] == way_ref:
				member = {
					'way_ref': len(ways) - 1,
					'role': area_member['role']
				}
				areas[ref]['members'].insert(member_index + 1, member)
				break


# Add new line to ways, including identifying and splitting existing ways

def process_line (ref, input_line, role):

	global near_ways

	# Just use polygon if not splitting into relations

	if not split:

		ways.append(create_way(input_line))
		member = {
			'way_ref': len(ways) - 1,
			'role': role,
		}
		areas[ref]['members'].append(member)

		return

	# Identify nearby ways to limit scope of matching

	input_way = create_way (input_line)
	near_ways = []
	way_index = -1

	for way in ways:
		way_index += 1
		if (way['max_lat'] > input_way['min_lat']) and (way['min_lat'] < input_way['max_lat']) and \
			(way['max_lon'] > input_way['min_lon']) and (way['min_lon'] < input_way['max_lon']):
			near_ways.append(way_index)

	log ("Role: %s\n" % role)
	log ("Line input: len %i\n" % len(input_way['line']))
	log ("Near ways: %s\n" % str(near_ways))

	# Iterate new line and identify existing (sub)lines + create new (sub)lines

	while len(input_line) > 1:

		# Find existing line

		near_index = -1
		node_index = 0

		while (near_index < len(near_ways) - 1) and (node_index < 1):
			near_index += 1
			line = ways[ near_ways[near_index] ]['line']
			reverse = False
			node_index = 0

			while (node_index < len(line)) and (node_index < len(input_line)) and \
				(input_line[node_index][0] == line[node_index][0]) and (input_line[node_index][1] == line[node_index][1]):
				node_index += 1

			# If not found, check reverse order

			if node_index <= 1:
				reverse = True
				node_index = 0

				while (node_index < len(line)) and (node_index < len(input_line)) and \
					(input_line[node_index][0] == line[len(line) - node_index - 1][0]) and \
					(input_line[node_index][1] == line[len(line) - node_index - 1][1]):
					node_index += 1

			node_index -= 1


		# Split existing line if needed + link to line

		if node_index > 0:

			found_way = near_ways[near_index]
			if node_index < len(line) - 1:
				if not reverse:
					split_way(found_way, node_index)
				else:
					log ("Reverse\n")
					split_way(found_way, len(line) - node_index - 1)
					found_way = len(ways) - 1

			member = {
				'way_ref': found_way,
				'role': role,
			}
			areas[ref]['members'].append(member)
			input_line = input_line[node_index:]

		else:
			# Check if split needed

			found_way, found_node = find_node(input_line[0])

			if (found_node is not None) and (found_node > 0) and (found_node < len(ways[found_way]['line']) - 1):
				split_way(found_way, found_node)

			else:
				# Identify new line

				found_node = None
				found_way = None
				node_index = 1

				while (node_index < len(input_line) - 1) and (found_node is None):
					coordinate = input_line[node_index]

					found_way, found_node = find_node(coordinate)

					if found_node is None:
						node_index += 1

				# Create new line

				if node_index > 0:
					new_way = create_way(input_line[ 0:node_index + 1 ])
					ways.append(new_way)
					member = {
						'way_ref': len(ways) - 1,
						'role': role
					}
					areas[ref]['members'].append(member)
					near_ways.append(len(ways) - 1)
					log ("New line: #%i len %s\n" % (len(ways) - 1, len(new_way['line'])))
					input_line = input_line[node_index:]

				# Split existing line

				if (found_node is not None) and (found_node > 0) and (found_node < len(ways[found_way]['line']) - 1):
					split_way(found_way, found_node)


# Produce tags

def tag_reserve (area):

	# Name tags

	short_name = area['navn'].strip()

	if area["offisieltnavn"] and area['offisieltnavn'] != short_name and " " in area['offisieltnavn']:
		name = area['offisieltnavn']
	elif area['verneform']:
		name = short_name + " " + verneform_description[ area['verneform'] ].lower()
	else:
		name = short_name

	official_name = name

	if name:
		split_position = name.find(" med ")
		if (split_position > 0) and (" med " not in short_name) and ("/" not in name):
			name = name[0:split_position]

		if area['verneplan'] == "verneplanSjøfugl":
			name.replace("dyr", "fugl")

	make_osm_line ("name", name.replace("/", " / ").replace("  ", " "))

	if short_name and short_name != name:
		make_osm_line ("short_name", short_name.replace("/", " / ").replace("  ", " "))

	if official_name and (official_name != name):
		make_osm_line ("official_name", official_name.replace("/", " / ").replace("  ", " "))

	# Other tags of area

	make_osm_line ("naturbase:iid", area['identifikasjon_lokalid'])
	make_osm_line ("naturbase:url", area['faktaark'])
	make_osm_line ("related_law", area['verneforskrift'])
	make_osm_line ("start_date", "%s-%s-%s" % (area['vernedato'][0:4], area['vernedato'][4:6], area['vernedato'][6:8]))

	if area['forvaltningsmyndighet']:
		make_osm_line ("operator", area['forvaltningsmyndighet'].replace("  ", " "))

	# Type of protected area

	protect_class = ""

	if area['iucn']:
		protect_class = iucn_code[ area['iucn'] ]
	
	if not protect_class and area['verneform']:
		verneform = area['verneform'].lower()
		if "naturreservat" in verneform:
			protect_class = "1a"
		elif "naturminne" in verneform:
			protect_class = "3"
		elif "fredning" in verneform or "biotop" in verneform:
			protect_class = "4"

	if protect_class:
		make_osm_line ("protect_class", protect_class)

	if protect_class in ["1a", "1b", "4"]:
		make_osm_line ("leisure", "nature_reserve")
		make_osm_line ("boundary", "protected_area")
	elif protect_class == "2":
		make_osm_line ("boundary", "national_park")
#		if not relation:
#			make_osm_line ("area", "yes")  # For rendering. Not needed since 2020
	else:
		make_osm_line ("boundary", "protected_area")

	if area['verneform'] and area['verneform'] in verneform_description:
		make_osm_line ("naturbase:verneform", verneform_description[ area['verneform'] ])

	if area['verneplan'] and area['verneplan'] in verneplan_description:
		make_osm_line ("naturbase:verneplan", verneplan_description[ area['verneplan'] ])

	# Notify if coding is not known

	if area['iucn'] and area['iucn'] not in iucn_code:
		message ("\t*** IUCN code not known: %s\n" % area['iucn'])
	if area['verneplan'] and area['verneplan'] not in verneplan_description:
		message ("\t*** Verneplan not known: %s\n" % area['verneplan'])
	if area['verneform'] and area['verneform'] not in verneform_description:
		message ("\t*** Verneform not known: %s\n" % area['verneform'])

	# Provide debug information

	if debug:
		if area['iucn']:
			make_osm_line ("IUCN", area['iucn'])
		if area['verneform']:
			make_osm_line ("VERNEFORM", area['verneform'])
		if area['verneplan']:
			make_osm_line ("VERNEPLAN", area['verneplan'])
		if area['navn']:
			make_osm_line ("NAVN", area['navn'])
		if area['offisieltnavn']:
			make_osm_line ("OFFISIELTNAVN", area['offisieltnavn'])

# Produce leisure area tags

def tag_leisure (area):

	make_osm_line ("boundary", "protected_area")
	make_osm_line ("protect_class", "21")
	make_osm_line ("naturbase:iid", area['identifikasjon_lokalid'])
	make_osm_line ("naturbase:url", area['faktaark'])

#	for key, value in iter(area.items()):
#		if key != "members":
#			make_osm_line(key, value)


# Main program

if __name__ == '__main__':

	# Load all protected areas

	message ("\nConverting Naturbase protected areas to OSM file\n")
	message ("Loading data ...")
	
	if len(sys.argv) > 1:
		filename = sys.argv[1].replace(".geojson", "").replace(".json", "")
	else:
		sys.exit("No input filename provided\n")

	file = open(filename + ".json")
	area_data = json.load(file)
	file.close()

	# Count polygons

	total_objects = 0
	for area in area_data['features']:
		if area['properties']['objtype'] in ["Naturvernområde", "SikraFriluftslivsområde"]:
			total_objects += 1

	message (" %s polygons\n" % total_objects)

	if debug:
		logfile = open (filename + "_log.txt", "w")

	# Create relations including splitting areas into member ways

	message ("Creating relations ...\n")

	areas = {}
	ways = []
	near_ways = []
	count_areas = 0

	for area in area_data['features']:
		info = area['properties']

		if info['objtype']in ["Naturvernområde", "SikraFriluftslivsområde"] and count_areas < 20000:
			total_objects -= 1
			message ("\r%i " % total_objects)
			polygon = area['geometry']['coordinates'][0]

			# Avoid circles

			if not((len(polygon) == 41) and (polygon[10][1] - polygon[30][1] < 0.000180) and (polygon[10][1] - polygon[30][1] > 0.000176)):
				ref = info['identifikasjon_lokalid']

				if not(ref in areas):
					areas[ref] = copy.deepcopy(area['properties'])
					areas[ref]['members'] = []
					count_areas += 1
					log ("\n\nArea: %s \n" % ref)

				process_line (ref, polygon, "outer")

				for polygon in area['geometry']['coordinates'][1:]:
					process_line (ref, polygon, "inner")

	message ("\r%i protected areas, %i ways\n" % (count_areas, len(ways)))

	# Produce OSM file header

	message ("Writing to file '%s.osm' ...\n" % filename)

	file = open (filename + ".osm", "w")
	file.write ('<?xml version="1.0" encoding="UTF-8"?>\n')
	file.write ('<osm version="0.6" generator="reserve2osm v%s" upload="false">\n' % version)

	node_id = -1000
	count = count_areas

	# Iterate all areas and produce OSM file
	# First all areas consisting of exactly one close way (no relation), then relations including all national parks

	for batch in [False, True]:

		for ref, area in iter(areas.items()):

			relation = (len(area['members']) > 1)

			if relation == batch:

				count -= 1
				message ("\r%i " % count)

				for member in area['members']:
					way_ref = member['way_ref']
					way = ways[way_ref]
					line = way['line']

					if not ("way_id" in way):

						# Start node

						old_node_id = find_node_id(line[0])

						if old_node_id:
							way['start_node1'] = old_node_id
						else:
							node_id -= 1
							file.write ('  <node id="%i" lat="%.7f" lon="%.7f" />\n' % (node_id, line[0][1], line[0][0]))
							way['start_node1'] = node_id
						
						# Middle nodes

						first_node = node_id - 1
						last_node = node_id

						for coordinate in line[1:-1]:
							node_id -= 1
							last_node = node_id
							file.write ('  <node id="%i" lat="%.7f" lon="%.7f" />\n' % (node_id, coordinate[1], coordinate[0]))

						way['start_node2'] = first_node
						way['end_node2'] = last_node

						# End node

						if (line[0][0] != line[-1][0]) or (line[0][1] != line[-1][1]):
							old_node_id = find_node_id(line[-1])
							if old_node_id:
								way['end_node1'] = old_node_id
							else:
								node_id -= 1
								file.write ('  <node id="%i" lat="%.7f" lon="%.7f" />\n' % (node_id, line[-1][1], line[-1][0]))
								way['end_node1'] = node_id
						else:
							way['end_node1'] = way['start_node1']

						# Output way if member of relation

						if relation:

							node_id -= 1
							file.write ('  <way id="%i">\n' % node_id)
							make_osm_line ("boundary", "protected_area")
							if debug:
								make_osm_line ("WAY_REF", str(member['way_ref']))
							way['way_id'] = node_id

							file.write ('    <nd ref="%i" />\n' % way['start_node1'])
							if first_node >= last_node:
								for node in range(first_node, last_node - 1, -1):
									file.write ('    <nd ref="%i" />\n' % node)
							file.write ('    <nd ref="%i" />\n' % way['end_node1'])

							file.write ('  </way>\n')

				# Header section of area

				node_id -= 1
				if relation:
					file.write ('  <relation id="%i" >\n' % node_id)
					make_osm_line ("type", "multipolygon")

				else:
					file.write ('  <way id="%i">\n' % node_id)
					ways[ area['members'][0]['way_ref'] ]['way_id'] = node_id

				if area['objtype'] == "Naturvernområde":
					tag_reserve (area)
				elif area['objtype'] == "SikraFriluftslivsområde":
					tag_leisure (area)

				# End section of area

				if not relation:
					if debug:
						make_osm_line ("WAY_REF", str(member['way_ref']))

					file.write ('    <nd ref="%i" />\n' % way['start_node1'])
					if first_node >= last_node:
						for node in range(way['start_node2'], way['end_node2'] - 1, -1):
							file.write ('    <nd ref="%i" />\n' % node)
					file.write ('    <nd ref="%i" />\n' % way['end_node1'])	

					file.write ('  </way>\n')

				else:
					for member in area['members']:
						file.write ('    <member type="way" ref="%i" role="%s" />\n' % (ways[member['way_ref']]['way_id'], member['role']))
					file.write ('  </relation>\n')


	# Produce OSM file footer

	file.write ('</osm>\n')
	file.close()

	if debug:
		logfile.close()

	message ("\n%i elements written to file\n" % (-1000 - node_id))
