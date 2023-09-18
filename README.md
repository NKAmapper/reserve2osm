# reserve2osm
Extracts protected areas from Naturbase and generates OSM file.

### Usage ###

<code>python reserve2osm.py [ naturvern | friluft | \<geoJSON filename\> ]</code>

Options:
* <code>friluft</code>: Get nature reserves, national parks and other protected nature areas.
* <code>friluft</code>: Get public leisure areas ("statlig sikra friluftsområder").
* <code>\<geoJSON filename\></code>: Create OSM relations for geoJSON input file.

### Notes ###

* Nature reserves, national parks and other protected areas are maintained in Naturbase by the [Norwegian Environment Agency](https://tema.miljodirektoratet.no/en/).
* Other data may be downloaded [here](https://karteksport.miljodirektoratet.no/). Select the whole country or a county, GeoJSON file format and any projection.
* The program will produce an OSM file with nested relations ready for uploading to or updating OSM.
  * The _protect_class_ tag is set according to the given IUCN class, or if missing dervied from given protection type.
  * The _name_ tag is set according to the given official name, or if missing derived from the given protection type, including with refinements for bird reserves and with simplifcations for very long names.
  * Boundary lines are simplified with a 0.2 factor.
* Please review in JOSM:
  * Use the Validation function in JOSM to check for potential errors.
  * Boundary lines with more than 2000 nodes will require splitting, for example at start/end of coastlines.
  * Self-intersecting polygons may require modification of "inner"/"outer" roles.
  * Please look for _"/"_ in names and add Sami/Norwegian language name tags.
  * When replacing existing tags please make sure that the Wikidata tag is preserved.

### References ###

* [Import wiki](https://wiki.openstreetmap.org/wiki/Import/Catalogue/Naturbase).
* [OSM file ready for uploading](https://www.jottacloud.com/s/059f4e21889c60d4e4aaa64cc857322b134).
* [Naturbase download page](https://karteksport.miljodirektoratet.no/).
