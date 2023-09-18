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
import math
import urllib.request
import time
from datetime import datetime
from xml.etree import ElementTree as ET


version = "2.0.0"

split = True 			# True for splitting polygons into network of realtions
geojson = False			# Output raw data in geojson file
debug = False			# Add a few extra tags
simplify = True 		# Simplify lines before output (less nodes)
simplify_factor = 0.2	# For reducing number of nodes
max_load = 10000		# Max features to load (per 1000), for debugging

# Avoid merging the following protected areas which have messy boundaries
no_merge_areas = [
	"VV00003632",		# Ytre Karlsøy marine verneområde
	"VV00001227"		# Bratthagen naturminne
] 

iucn_code = {
	'IUCN_IA':		'1a',
	'IUCN_IB':		'1b',
	'IUCN_II':		'2',
	'IUCN_III':		'3',
	'IUCN_IV':		'4',
	'IUCN_V':		'5',
	'IUCN_VI':		'6',
	'IkkeVurdert': 	''
}

verneform_description = {
	'Biotopvern':									'Biotopvernområde',  # BV
	'BiotopvernSvalbard':							'Biotopvernområde',  # BVS, Svalbardmiljøloven
	'BiotopvernVilt':								'Biotopvernområde',  # BVV, etter viltloven
	'Dyrefredningsomrade':							'Dyrefredningsområde', # DO
	'Dyrelivsfredning':								'Dyrelivsfredning',  # D
	'GeotopvernSvalbard':							'Geotopvernområde',  # GVS, Svalbardmiljøloven
	'Landskapsvernomraade':							'Landskapsvernområde',  # LVO
	'LandskapsvernomraadeBiotopvern':				'Landskapsvernområde med biotopvern',
	'LandskapsvernomraadeDyrelivsfredning':			'Landskapsvernområde med dyrelivsfredning',  # LVOD
	'LandskapsvernomraadePlantelivsfredning':		'Landskapsvernområde med plantelivsfredning',  # LVOP
	'LandskapsvernomraadePlanteOgDyrelivsfredning':	'Landskapsvernområde med plante- og dyrelivsfredning',  # LVOPD
#	'': 											'Landskapsvernområde med dyre- og plantelivsfredning',  # LVODP, typo?
	'MarintVerneomraade':							'Marint verneområde',  # NAVA, annet lovverk
#	'':												'Marint verneområde',  # MAV, naturmangfoldloven
#	'':												'Midlertidig vernet',  # MIV  
	'Nasjonalpark':									'Nasjonalpark',  # NP
	'NasjonalparkSvalbard':							'Nasjonalpark',  # NPS, Svalbardmiljøloven
	'Naturminne':									'Naturminne',    # NM
	'Naturreservat':								'Naturreservat',  # NR
	'NaturreservatJanMayen':						'Naturreservat',
	'NaturreservatSvalbard':						'Naturreservat',  # NRS, Svalbardmiljøloven
	'Plantefredningsomraade':						'Plantefredningsområde',  # PO
	'Plantelivsfredning':							'Plantelivsfredning',  # P
	'PlanteOgDyrefredningsomraade':					'Plante- og dyrefredningsområde',  # PDO
	'PlanteOgDyrelivsfredning':						'Plante- og dyrelivsfredning'  # PD
}

verneplan_description = {   
	'VerneplanNasjonalpark':	'Nasjonalpark',
	'VerneplanVatmark':			'Våtmark',
	'VerneplanMyr':				'Myr',
	'VerneplanLoevskog':		'Løvskog',
	'VerneplanSjoefugl':		'Sjøfugl',
	'Skogvern':					'Skog',
	'MarinVerneplan':			'Marin',
	'AnnetVern':  				'',
	'Kvartaergeologi':			'Kvartærgeologi',
	'Fossiler':					'Fossiler',
	'IkkeVurdert':				''
}



# Output message

def message (line):

	sys.stdout.write (line)
	sys.stdout.flush()



# Compute closest distance from point p3 to line segment [s1, s2].
# Works for short distances.

def line_distance(s1, s2, p3):

	x1, y1, x2, y2, x3, y3 = map(math.radians, [s1[0], s1[1], s2[0], s2[1], p3[0], p3[1]])  # Note: (x,y)

	# Simplified reprojection of latitude
	x1 = x1 * math.cos( y1 )
	x2 = x2 * math.cos( y2 )
	x3 = x3 * math.cos( y3 )

	A = x3 - x1
	B = y3 - y1
	dx = x2 - x1
	dy = y2 - y1

	dot = (x3 - x1)*dx + (y3 - y1)*dy
	len_sq = dx*dx + dy*dy

	if len_sq != 0:  # in case of zero length line
		param = dot / len_sq
	else:
		param = -1

	if param < 0:
		x4 = x1
		y4 = y1
	elif param > 1:
		x4 = x2
		y4 = y2
	else:
		x4 = x1 + param * dx
		y4 = y1 + param * dy

	# Also compute distance from p to segment

	x = x4 - x3
	y = y4 - y3
	distance = 6371000 * math.sqrt( x*x + y*y )  # In meters

	'''
	# Project back to longitude/latitude

	x4 = x4 / math.cos(y4)

	lon = math.degrees(x4)
	lat = math.degrees(y4)

	return (lon, lat, distance)
	'''

	return distance



# Simplify line, i.e. reduce nodes within epsilon distance.
# Ramer-Douglas-Peucker method: https://en.wikipedia.org/wiki/Ramer–Douglas–Peucker_algorithm

def simplify_line(line, epsilon):

	dmax = 0.0
	index = 0
	for i in range(1, len(line) - 1):
		d = line_distance(line[0], line[-1], line[i])
		if d > dmax:
			index = i
			dmax = d

	if dmax >= epsilon:
		new_line = simplify_line(line[:index+1], epsilon)[:-1] + simplify_line(line[index:], epsilon)
	else:
		new_line = [line[0], line[-1]]

	return new_line



# Produce tags based on properties from Naturbase (info)

def get_tags(info):

	tags = {}

	if datatype == "naturvern":  # Tag nature reserves

		# Name tags

		short_name = info['navn'].strip()

		if info["offisieltNavn"] and info['offisieltNavn'] != short_name and " " in info['offisieltNavn']:
			name = info['offisieltNavn']
		elif info['verneform']:
			name = short_name + " " + verneform_description[ info['verneform'] ].lower()
		else:
			name = short_name

		official_name = name

		if name:
			split_position = name.find(" med ")
			if (split_position > 0) and (" med " not in short_name) and ("/" not in name):
				name = name[0:split_position]

			if info['verneplan'] == "VerneplanSjoefugl":
				name = name.replace("dyr", "fugl")

		tags['name'] = name.replace("/", " / ").replace("  ", " ")

		if short_name and short_name != name:
			tags['short_name'] = short_name.replace("/", " / ").replace("  ", " ")

		if official_name and official_name != name:
			tags['official_name'] = official_name.replace("/", " / ").replace("  ", " ")

		# Other tags of area

		tags['ref:naturvern'] = info['naturvernId']
		tags['naturbase:url'] = info['faktaark']
		tags['related_law'] = info['verneforskrift']

		if info['vernedato']:
			tags['start_date'] = datetime.fromtimestamp(info['vernedato'] / 1000).isoformat()[:10]  # Milliseconds

		if info['forvaltningsmyndighet']:
			tags['operator'] = info['forvaltningsmyndighet'].replace("  ", " ")

		# Type of protected area

		protect_class = ""

		if info['iucn']:
			protect_class = iucn_code[ info['iucn'] ]
		
		if not protect_class and info['verneform']:
			verneform = info['verneform'].lower()
			if "naturreservat" in verneform:
				protect_class = "1a"
			elif "naturminne" in verneform:
				protect_class = "3"
			elif "fredning" in verneform or "biotop" in verneform:
				protect_class = "4"

		if protect_class:
			tags['protect_class'] = protect_class

		if protect_class in ["1a", "1b", "4"]:
			tags['leisure'] = "nature_reserve"
			tags['boundary'] = "protected_area"
		elif protect_class == "2":
			tags['boundary'] = "national_park"
		else:
			tags['boundary'] = "protected_area"

		if info['verneform'] and info['verneform'] in verneform_description:
			tags['naturbase:verneform'] = verneform_description[ info['verneform'] ]

		if info['verneplan'] and info['verneplan'] in verneplan_description:
			tags['naturbase:verneplan'] = verneplan_description[ info['verneplan'] ]

		tags['KOMMUNE'] = info['kommune'].replace(",", ", ")

		# Notify if coding is not known

		if info['iucn'] and info['iucn'] not in iucn_code:
			message ("\t*** IUCN code not known: %s\n" % info['iucn'])
		if info['verneplan'] and info['verneplan'] not in verneplan_description:
			message ("\t*** Verneplan not known: %s\n" % info['verneplan'])
		if info['verneform'] and info['verneform'] not in verneform_description:
			message ("\t*** Verneform not known: %s\n" % info['verneform'])

		# Provide debug information

		if debug:
			if info['iucn']:
				tags['IUCN'] = info['iucn']
			if info['verneform']:
				tags['VERNEFORM'] = info['verneform']
			if info['verneplan']:
				tags['VERNEPLAN'] = info['verneplan']
			if info['navn']:
				tags['NAVN'] = info['navn']
			if info['offisieltNavn']:
				tags['OFFISIELTNAVN'] = info['offisieltNavn']

	else:  # Tag protected leisure areas

		tags['boundary'] = "protected_area"
		tags['protect_class'] = "21"
		tags['ref:friluft'] = info['friluftId']
		tags['naturbase:url'] = info['faktaark']
		tags['name'] = info['omraadeNavn']
		tags['BESKRIVELSE'] = info['omraadeBeskrivelse']

	# Check for empty tags

	for key in list(tags.keys()):
		if tags[key] == "" or tags[key] is None:
			del tags[key]

	return tags



# Create member record

def get_member(way_ref, role):

	member = {
		'way_ref': way_ref,
		'role': role			
	}
	return member



# Create new way record, including bbox

def create_way(line):

	new_way = {
		'line': line,
		'bbox_min': [0,0],
		'bbox_max': [0,0]
	}

	for i in [0, 1]:
		new_way['bbox_min'][i] = min(point[i] for point in line)
		new_way['bbox_max'][i] = max(point[i] for point in line)

	return new_way



# Decompose outer/inner polygon into way segments

def process_polygon(ref, input_polygon, role):

	polygon = [ (point[0], point[1]) for point in input_polygon ]

	# Skip matching if blacklisted

	if not split or ref in no_merge_areas:
		ways.append(create_way(polygon))
		areas[ref]['members'].append(get_member(len(ways) - 1, role))
		ways[-1]['nomerge'] = True
		return

	# Build list of ways intersecting with polygon to speed up matching

	input_way = create_way(polygon)
	polygon_set = set(polygon)
	near_ways = []

	for way_ref, way in enumerate(ways):
		if (way['bbox_max'][0] >= input_way['bbox_min'][0] and way['bbox_min'][0] <= input_way['bbox_max'][0]
				and way['bbox_max'][1] >= input_way['bbox_min'][1] and way['bbox_min'][1] <= input_way['bbox_max'][1]
				and "nomerge" not in way
				and len(polygon_set.intersection(way['line'])) > 0):  # Even for one node (touching rings)
			near_ways.append(way_ref)

	# Create new way if no matching ways

#	if not near_ways:
#		ways.append(create_way(polygon))
#		areas[ref]['members'].append(get_member(len(ways) - 1, role))
#		return		

	# Loop intersecting ways and split/match

	junctions = set()
	match_ways = []

	for way_ref in near_ways:
		way = ways[ way_ref ]
		way_line = way['line']
		way_set = set(way['line'])

		# Quick exit for exact match

		if way_set == polygon_set:
			areas[ ref ]['members'].append(get_member(way_ref, role))
			return

		# Discover junctions

		for i in range(1, len(polygon) - 1):
			if polygon[i] in way_set and (polygon[i-1] not in way_set or polygon[i+1] not in way_set):
				junctions.add(polygon[i])

		for i in range(1, len(way_line) - 1):
			if way_line[i] in polygon_set and (way_line[i-1] not in polygon_set or way_line[i+1] not in polygon_set):
				junctions.add(way_line[i])			

		if not junctions:
			continue  # No match

		for i in [0,-1]:
			junctions.add(polygon[i])
			junctions.add(way_line[i])

		# Split way at each junction

		way_refs = []
		remaining_line = way_line.copy()

		while remaining_line:
			new_line = [ remaining_line.pop(0) ]
			while remaining_line and remaining_line[0] not in junctions:
				new_line.append(remaining_line.pop(0))

			if remaining_line:
				new_line.append(remaining_line[0])

			if len(new_line) > 1 :
				if not way_refs:
					way['line'] = new_line
					way_refs.append(way_ref)
				else:
					ways.append(create_way(new_line))
					way_refs.append(len(ways) - 1)

				if len(polygon_set.intersection(new_line)) > 1:
					match_ways.append(way_refs[-1])

		# Update members which already refer to way

		if len(way_refs) > 1:
			for area in areas.values():
				for i, member in enumerate(area['members']):
					if member['way_ref'] == way_ref:
						new_members = []
						for member_ref in way_refs:
							new_members.append(get_member(member_ref, member['role']))
						area['members'][i:i+1] = new_members
						break

	# Add self-intersecting junctions for polygon

	polygon_set = set([polygon[0], polygon[-1]])
	for node in polygon[1:-1]:
		if node in polygon_set:
			junctions.add(node)
		polygon_set.add(node)

	# Split polygon at junctions

	segments = []
	remaining_line = polygon.copy()

	while remaining_line:
		new_line = [ remaining_line.pop(0) ]
		while remaining_line and remaining_line[0] not in junctions:
			new_line.append(remaining_line.pop(0))

		if remaining_line:
			new_line.append(remaining_line[0])

		if len(new_line) > 1 and not(len(new_line) == 2 and new_line[0] == new_line[-1]):
			segments.append(new_line)

	# Match polygon segments with ways, or create new ways if no match

	way_refs = []
	for segment in segments:
		found = False
		for way_ref in match_ways:
			if set(segment) == set(ways[ way_ref ]['line']):
				areas[ ref ]['members'].append(get_member(way_ref, role))
				match_ways.remove(way_ref)
				found = True
				break

		if not found:
			ways.append(create_way(segment))
			areas[ ref ]['members'].append(get_member(len(ways) - 1, role))



# Create data structure for feature and decompose line segments

def process_feature (feature):

	global ref_id

	info = feature['properties']

	if feature['geometry']['type'] == "MultiPolygon":
		multipolygon = feature['geometry']['coordinates']
	else:
		multipolygon = [ feature['geometry']['coordinates'] ]

	# Avoid small circles representing a point

	coordinates = multipolygon[0][0]
	if (len(coordinates) == 41
			and coordinates[10][1] - coordinates[30][1] < 0.000180
			and coordinates[10][1] - coordinates[30][1] > 0.000176):
		return

	# Init data structure.
	# Areas may appear multiple times as geojson features, one for each outer area

	if datatype == "geojson":
		ref_id += 1
		ref = ref_id
	else:
		ref = info[ datatype + 'Id' ]

	if ref not in areas:
		areas[ ref ] = {
			'members': [],
			'tags': {}
		}
		if datatype == "geojson":
			for key, value in iter(info.items()):
				if value:
					areas[ ref ]['tags'][ key ] = str(value)
		else:
			areas[ ref ]['tags'] = get_tags(info)
			if ref in no_merge_areas:
				areas[ ref ]['tags']['NOTE'] = "Polygonet er ikke flettet med andre verneområder"

	# Create way segments for polygon/multipolygon.
	# A multipolygon is a list of polygons, each with one outer and multiple inner patches

	for polygon in multipolygon:
		process_polygon (ref, polygon[0], "outer")
		for inner in polygon[1:]:
			process_polygon (ref, inner, "inner")



# Combine non-branching ways into longer ways

def combine_ways():

	# Build dict of junctions with set of all connected ways

	junctions = {}
	for way_ref, way in enumerate(ways):
		way['parents'] = set()
		if "nomerge" not in way:
			for node in [ way['line'][0], way['line'][-1] ]:
				if node not in junctions:
					junctions[ node ] = []  # Set not used due to self-intersecting rings
				junctions[ node ].append(way_ref)

	# Build info on which areas uses each way

	for area_ref, area in iter(areas.items()):
		for member in area['members']:
			ways[ member['way_ref'] ]['parents'].add(area_ref)

	# Iterate junctions and combine if no branching (2 ways with identical parents)

	count = 0
	for node in junctions.keys():
		junction = junctions[ node ]

		if len(junction) == 2:
			way_ref1 = list(junction)[0]
			way_ref2 = list(junction)[1]

			if way_ref1 != way_ref2 and ways[ way_ref1 ]['parents'] == ways[ way_ref2 ]['parents']:
				line1 = ways[ way_ref1 ]['line']
				line2 = ways[ way_ref2 ]['line']

				# Connect at node position, even for ring. Ways have same direction.
				if line1[-1] == node:
					new_line = line1 + line2[1:]  
				else:
					new_line = line2 + line1[1:]

				ways[ way_ref1 ]['line'] = new_line
				ways[ way_ref2 ] = { 'delete': True }  # Mark for no later output
				count += 1

				# Swap deleted way with combined way in all relevant junctions
				for node2 in junctions.keys():
					while way_ref2 in junctions[ node2 ]:
						junctions[ node2 ].remove(way_ref2)
						junctions[ node2 ].append(way_ref1)

	# Remove deleted ways from multipolygon members

	for area in areas.values():
		for member in area['members'][:]:
			if "delete" in ways[ member['way_ref'] ]:
				area['members'].remove(member)
				if debug:
					area['tags']['KOMBINERT'] = "yes"

	message ("Combined %i contiguous ways\n" % count)



# Simplify line geometry for all ways.

def simplify_ways():

	message ("Simplify geometry ...\n")
	for way in ways:
		if "delete" not in way and len(way['line']) > 3:
			new_line = simplify_line(way['line'], simplify_factor)

			# Avoid collapsing tiny polygons, including with two tiny segments
			if (way['line'][0] == way['line'][-1] and len(new_line) > 3
					or way['line'][0] != way['line'][-1] and len(new_line) > 2):
				way['line'] = new_line



# Load data from Naturbase

def load_data(datatype):

	if "geojson" in datatype:
		# Open geojson file (any content)

		file = open(datatype)
		geojson_data = json.load(file)
		file.close()
		features.extend(geojson_data['features'])

	else:
		# Load data from Miljødirektoratet REST server

		if datatype == "naturvern":
			endpoint = "https://kart.miljodirektoratet.no/arcgis/rest/services/vern/mapserver/0/"
		elif datatype == "friluft":
			endpoint = "https://kart.miljodirektoratet.no/arcgis/rest/services/friluftsliv_statlig_sikra/mapserver/0/"
		else:
			sys.exit("Data source '%s' not known\n" % datatype)

		url = endpoint + "query?where=1=1&outFields=*&geometryPrecision=7&f=geojson&resultRecordCount=1000"
		filename = datatype.lower()
		area_data = []
		page_data = { 'exceededTransferLimit': True }
		count = 0

		while "exceededTransferLimit" in page_data and count < max_load:
			request = urllib.request.Request(url + "&resultOffset=%i" % count)  # Paged data
			file = urllib.request.urlopen(request)
			page_data = json.load(file)
			file.close()
			area_data.extend(page_data['features'])
			count += len(page_data['features'])

		# Output raw data
		if geojson:
			file = open(filename + "_raw.geojson", "w")
			collection = {
				'type': 'FeatureCollection',
				'features': area_data
			}
			json.dump(collection, file, indent=2, ensure_ascii=False)
			file.close()

		features.extend(area_data)



# Indent XML output

def indent_tree(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent_tree(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i



# Save osm file

def output_file(filename):

	message ("Save to '%s' file...\n" % filename)

	osm_node_ids = {}  # Will contain osm_id of each common node
	relation_count = 0
	way_count = 0
	node_count = 0

	osm_root = ET.Element("osm", version="0.6", generator="reserve2osm v"+version, upload="false")
	osm_id = -1000

	# Create common nodes at intersections

	for way in ways:
		if "delete" not in way:
			for node in [ way['line'][0], way['line'][-1] ]:
				if node not in osm_node_ids:
					osm_id -= 1
					osm_node = ET.Element("node", id=str(osm_id), action="modify", lat=str(node[1]), lon=str(node[0]))
					osm_root.append(osm_node)
					osm_node_ids[ node ] = osm_id
					node_count += 1

	# Create ways with remaining nodes

	for way_ref, way in enumerate(ways):
		if "delete" not in way:
			osm_id -= 1
			osm_way = ET.Element("way", id=str(osm_id), action="modify")
			osm_root.append(osm_way)
			way['osm_id'] = osm_id
			way['etree'] = osm_way
			way_count += 1

			for node in way['line']:
				if node in osm_node_ids:
					osm_nd = ET.Element("nd", ref=str(osm_node_ids[ node ]))
				else:
					osm_id -= 1
					osm_node = ET.Element("node", id=str(osm_id), action="modify", lat=str(node[1]), lon=str(node[0]))
					osm_root.append(osm_node)
					osm_nd = ET.Element("nd", ref=str(osm_id))
					node_count += 1
				osm_way.append(osm_nd)

			if debug:
				osm_tag = ET.Element("tag", k="WAY_REF", v=str(way_ref))
				osm_way.append(osm_tag)


	# Create areas

	for area in areas.values():

		# Output way if possible to avoid relation
		if len(area['members']) == 1:
			way = ways[ area['members'][0]['way_ref'] ]
			osm_area = way['etree']  # Get way for tag output below
			way['tagged'] = True

		else:
			# Output relation
			osm_id -= 1
			osm_area = ET.Element("relation", id=str(osm_id), action="modify")
			osm_root.append(osm_area)
			relation_count += 1

			for member in area['members']:
				way = ways[ member['way_ref'] ]
				osm_member = ET.Element("member", type="way", ref=str(way['osm_id']), role=member['role'])
				osm_area.append(osm_member)

			if datatype == "geojson":
				osm_tag = ET.Element("tag", k="type", v="multipolygon")
			else:
				osm_tag = ET.Element("tag", k="type", v="boundary")
			osm_area.append(osm_tag)

		# Output tags
		for key, value in iter(area['tags'].items()):
			osm_tag = ET.Element("tag", k=key, v=value)
			osm_area.append(osm_tag)

	# Add boundary tag to untagged ways

	if datatype != "geojson":
		for way in ways:
			if "delete" not in way and "tagged" not in way:
				osm_tag = ET.Element("tag", k="boundary", v="protected_area")
				way['etree'].append(osm_tag)			

	osm_root.set("upload", "false")
	indent_tree(osm_root)
	osm_tree = ET.ElementTree(osm_root)
	osm_tree.write(filename, encoding='utf-8', method='xml', xml_declaration=True)

	message ("\t%i relations, %i ways, %i nodes saved\n" % (relation_count, way_count, node_count))



# Main program

if __name__ == '__main__':

	# Load all protected areas

	start_time = time.time()
	message ("\nConverting Naturbase protected areas to OSM file\n")
	message ("Loading data ...")

	features = []  # Will contain geojson features for all protected areas

	datatype = ""
	if len(sys.argv) > 1:
		if ".geojson" in sys.argv[1]:
			datatype = "geojson"
			filename = sys.argv[1].lower().replace(".geojson", "") + "_relations"
			load_data(sys.argv[1].lower())  # Load file
		elif sys.argv[1] == "naturvern":
			datatype = "naturvern"
			filename = "naturvernområder"
			load_data("naturvern")
		elif sys.argv[1] == "friluft":
			datatype = "friluft"
			filename = "friluftsområder"
			load_data("friluft")

	if not datatype:
		sys.exit("Please provide 'naturvern', 'friluft' or geojson filename\n")

	count = len(features)
	message (" %i %sområder\n" % (count, datatype))

	# Create relations including splitting areas into member ways

	message ("Creating relations ...\n")

	areas = {}  # All protected areas
	ways = []   # All way segments (members of area multipolygons)
	ref_id = 0  # Area id for geojson input

	for feature in features:
		count -= 1
		message ("\r%i " % count)
		process_feature(feature)

	message ("\r \t%i protected areas, %i ways\n" % (len(areas), len(ways)))

	# Simplify ways and output file

	if split:
		combine_ways()

	if simplify:
		simplify_ways()

	output_file(filename + ".osm")

	duration = time.time() - start_time
	message ("Time: %i seconds\n\n" % duration)
