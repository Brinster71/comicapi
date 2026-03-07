
# Comic Metadata Reference

## Serialization Formats
| Ecosystem | Storage Format |
|---|---|
| ComicRack / ComicInfo | XML |
| ComicBookLover (CBL) | XML |
| CoMet | XML |
| ComicVine API | JSON |
| Filename-derived metadata | N/A (string parsing rules) |

---

# 1. Common Field List Mapping Across Ecosystems

| Common Field | ComicRack (ComicInfo.xml) | ComicBookLover | CoMet | ComicVine API |
|---|---|---|---|---|
Series | Series | series | series | volume.name |
Title | Title | title | title | name |
Issue Number | Number | issue | issue | issue_number |
Volume | Volume | volume | volume | volume.start_year |
Issue Count | Count | issueCount | issueCount | volume.count_of_issues |
Publisher | Publisher | publisher | publisher | publisher.name |
Imprint | Imprint | imprint | imprint | publisher.imprint |
Year | Year | year | year | cover_date |
Month | Month | month | month | cover_date |
Day | Day | day | day | cover_date |
Writer | Writer | writer | writer | person_credits |
Penciller | Penciller | penciller | penciller | person_credits |
Inker | Inker | inker | inker | person_credits |
Colorist | Colorist | colorist | colorist | person_credits |
Letterer | Letterer | letterer | letterer | person_credits |
Editor | Editor | editor | editor | person_credits |
Cover Artist | CoverArtist | coverArtist | coverArtist | person_credits |
Summary | Summary | summary | summary | description |
Characters | Characters | characters | characters | character_credits |
Teams | Teams | teams | teams | team_credits |
Locations | Locations | locations | locations | location_credits |
Story Arc | StoryArc | storyArc | storyArc | story_arc_credits |
Tags | Tags | tags | tags | tags |
ISBN | ISBN | isbn | isbn | isbn |
Barcode | Barcode | barcode | barcode | barcode |
Page Count | PageCount | pageCount | pageCount | page_count |

---

# 2. Full Field Lists by Ecosystem

## ComicRack / ComicInfo.xml
### Core Identification
Title
Series
Number
Count
Volume
AlternateSeries
AlternateNumber
AlternateCount

### Publication
Publisher
Imprint
Year
Month
Day
LanguageISO
Format
AgeRating

### Credits
Writer
Penciller
Inker
Colorist
Letterer
CoverArtist
Editor
Translator

### Story Content
Summary
Notes
Tags
Characters
Teams
Locations
StoryArc
StoryArcNumber

### Database IDs
Web
GTIN
Barcode
ISBN

### Reading Order / Organization
SeriesGroup
ScanInformation
PageCount

### Page Metadata
Pages
Page Type
Image Index

---

## ComicBookLover Metadata

### Identification
title
series
issue
volume
alternateSeries

### Publication
publisher
imprint
year
month
day
format
edition

### Credits
writer
penciller
inker
colorist
letterer
editor
coverArtist

### Story Data
summary
characters
teams
locations
tags
storyArc

### Misc
notes
scanInformation
web

---

## CoMet Metadata

### Identification
title
series
issue
volume
issueCount

### Publication
publisher
imprint
date
year
month
day
format
language

### Credits
writer
penciller
inker
colorist
letterer
editor
coverArtist

### Content
summary
characters
teams
locations
genre
storyArc
tags

### External IDs
comicvineID
isbn
barcode

### File Metadata
pageCount
fileFormat

---

# 3. Filename / Folder Metadata Variables

These variables are commonly used by comic library software when extracting metadata from filenames or folders.

| Variable | Meaning |
|---|---|
series | comic series name |
title | issue title |
issue | issue number |
volume | series volume |
year | publication year |
month | publication month |
day | publication day |
publisher | publisher name |
imprint | imprint |
writer | writer name |
penciller | penciller name |
inker | inker name |
colorist | colorist name |
letterer | letterer name |
editor | editor |
characters | featured characters |
teams | teams appearing |
locations | locations |
storyarc | story arc |
arc_number | position in arc |
variant | variant cover indicator |
edition | edition type |
language | language code |
format | digital / TPB / omnibus |
scan_group | scanning group |
page_count | total pages |

---

# Example Filename Parsing Pattern

Example filename:

Batman (2016) v3 050 (Variant) (DC)

Variables extracted:

series=Batman
year=2016
volume=3
issue=50
variant=Variant
publisher=DC

---

# Example ComicInfo XML

<ComicInfo>
  <Series>Batman</Series>
  <Number>50</Number>
  <Volume>2016</Volume>
  <Writer>Tom King</Writer>
  <Publisher>DC Comics</Publisher>
</ComicInfo>
