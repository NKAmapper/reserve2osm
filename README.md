# reserve2osm
Extracts protected areas from Naturbase and generates OSM file.

### Usage ###

<code>python reserve2osm.py [input_file]</code>

### Notes ###

* Nature reserves, national parks and other protected areas are maintained in Naturbase by the [Norwegian Environment Agency](https://tema.miljodirektoratet.no/en/).
* The latest data from Naturbase may be downloaded [here](https://karteksport.miljodirektoratet.no/). Select the whole country or a county, GeoJSON file format and any projection.
* The filename from Naturbase _without_ the _".json"_ extension is the only input parameter to the program.
* The program will produce an OSM file with nested relations ready for uploading to or updating OSM.
  * The _protect_class_ tag is set according to the given IUCN class, or if missing dervied from given protection type.
  * The _name_ tag is set according to the given official name, or if missing derived from the given protection type, including with refinements for bird reserves and with simplifcations for very long names.
* Please review in JOSM:
  * All boundary lines are reproduced as given from Naturbase. Resulting node density is high for coastlines and rivers/streams. Simplification with factor 0.1-0.2 may or may not be desired.
  * Boundary lines with more than 2000 nodes will require splitting, for example at start/end of coastlines.
  * A few nodes will be duplicates because of coordinate rounding in OSM. Please identify them using the JOSM validator function (automatic fix).
  * Please look for _"/"_ in names and add Sami/Norwegian language name tags.
  * When replacing existing tags please make sure that the Wikidata tag is preserved.

### References ###

* [Import wiki](https://wiki.openstreetmap.org/wiki/Import/Catalogue/Naturbase).
* [OSM file ready for uploading](https://drive.google.com/drive/folders/1LCQbqSB6ouMePkkF6VsvwePD_uwweq-D?usp=sharing).
* [Naturbase download page](https://karteksport.miljodirektoratet.no/).
