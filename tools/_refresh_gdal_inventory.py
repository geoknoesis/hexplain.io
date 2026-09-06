"""Explicit online refresh; ordinary CI validates the saved inventory offline."""
import hashlib,json,urllib.request,urllib.parse
from pathlib import Path
from datetime import datetime,timezone

families={
'grid': 'GTiff COG BMP ENVI EHdr ISCE PNM PAux MFF MFF2 SAGA ERS EIR ROI RRASTER KRO LAN BYN BT ACE2 GSB GTX NTv2 NWT_GRD GSC IDA IGNFHeightASCIIGrid SNODAS GenBin DOQ1 DOQ2 DTED DIPEx USGSDEM LCP',
'hierarchical-array':'HDF4 HDF5 netCDF Zarr BAG KEA TileDB HFA',
'segmented-imagery':'NITF RPFTOC ADRG ECRGTOC CEOS SAR_CEOS AIRSAR COASP COSAR CPG CPHD',
'manifest-bundle':'PDS PDS4 ISIS2 ISIS3 VICAR DIMAP SAFE SENTINEL2 RS2 RCM TSX TIL STACIT STACTA',
'encoded-image':'PNG JPEG GIF BIGGIF WEBP JP2OpenJPEG JP2KAK JP2ECW JP2MrSID JPEG2000 JXL AVIF HEIF GTiff COG BASISU KTX2 DDS EXR GRIB',
'indexed-container':'GPKG SQLite MBTiles Rasterlite Rasterlite2 OpenFileGDB FileGDB PGeo PMTiles',
'vector-records':'ESRI Shapefile|FlatGeobuf|Arrow|Parquet|MVT|OSM|S57|DGN|DXF|CAD|DWG|MapInfo File|AVCBin|GPSBabel|Selafin',
'tree-document':'GeoJSON GeoJSONSeq ESRIJSON TopoJSON JSONFG GML GMLAS KML LIBKML GPX GeoRSS ODS XLSX',
}
def family_names(v):return v.split('|') if '|' in v else v.split()
# Pin a released documentation version; never silently mix a moving stable index with master.
import re, concurrent.futures
revision='v3.13.3'
base=f'https://raw.githubusercontent.com/OSGeo/gdal/{revision}/doc/source/drivers/'
sources=[];jobs=[]
for kind in ['raster','vector']:
    url=base+kind+'/index.rst'
    raw=urllib.request.urlopen(url,timeout=60).read()
    block=raw.decode().split('.. toctree::',1)[1].split('.. ',1)[0]
    pages=[line.strip() for line in block.splitlines() if re.fullmatch(r'   [a-zA-Z0-9_]+',line)]
    sources.append({'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'document_pages':len(pages)})
    jobs.extend((kind,page) for page in pages)
def read_page(job):
    kind,page=job;url=base+kind+'/'+page+'.rst'
    raw=urllib.request.urlopen(url,timeout=60).read();s=raw.decode()
    names=re.findall(r'^\.\. shortname::\s*(.+)$',s,re.M)
    name=' / '.join(names) if names else page
    return {'key':kind+':'+page,'kind':kind,'name':name,'source':url,
       'documentation':'https://gdal.org/en/stable/drivers/'+kind+'/'+page+'.html',
       'sha256':hashlib.sha256(raw).hexdigest(),
       'capability_families':[k for k,v in families.items() if any(n in family_names(v) for n in names)],
       'assessment':'not-runtime-verified'}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:drivers=list(pool.map(read_page,jobs))
assert len(drivers)>200 and len({d['key'] for d in drivers})==len(drivers)
out=Path(__file__).resolve().parent.parent/'specification/coverage/gdal-drivers.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({'gdal_release':revision,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'scope':'Released documentation pages, not unique binary formats or certified support. Multiple drivers may share a page. Family tags are planning inferences; an empty list means unassessed.','sources':sources,'drivers':drivers},indent=2)+'\n',encoding='utf-8')
print(f'Saved {len(drivers)} GDAL documentation entries at {revision}')
