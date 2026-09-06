from pathlib import Path
import re,html
p=Path('tools/specgraph.py');s=p.read_text(encoding='utf-8').replace('*_ROOTS,','*sorted(glob.glob("specification/*/*.ttl")),').replace('return _existing(_SHAPE_FILES)','return ontology_paths()')
p.write_text(s,encoding='utf-8')
p=Path('specification/vdv/video.ttl');s=p.read_text(encoding='utf-8')
s=s.replace('sh:targetSubjectsOf vdv:frameRate ;','sh:targetClass vdv:VideoStream, vdv:VideoTrack ;\n    sh:targetSubjectsOf vdv:frameRate, vdv:frameCount, vdv:aspectRatio, vdv:scanType, vdv:audioChannels, vdv:frameRateNumerator, vdv:frameRateDenominator ;')
numeric='sh:or ( [ sh:datatype xsd:decimal ] [ sh:datatype xsd:integer ] )'
s=s.replace('sh:path vdv:frameRate ; sh:nodeKind sh:Literal',f'sh:path vdv:frameRate ; {numeric} ; sh:minExclusive 0')
s=s.replace('sh:path atime:duration ; sh:nodeKind sh:Literal',f'sh:path atime:duration ; {numeric} ; sh:minInclusive 0')
s=s.replace('sh:property [ sh:path vdv:scanType', '''sh:property [ sh:path vdv:frameCount ; sh:or ( [ sh:datatype xsd:integer ] [ sh:datatype xsd:unsignedLong ] ) ; sh:minInclusive 0 ; sh:maxInclusive 18446744073709551615 ; sh:maxCount 1 ] ;
    sh:property [ sh:path vdv:audioChannels ; sh:or ( [ sh:datatype xsd:integer ] [ sh:datatype xsd:positiveInteger ] ) ; sh:minExclusive 0 ; sh:maxCount 1 ] ;
    sh:property [ sh:path vdv:scanType''')
s += '''
# Exact nominal rate. For variable-rate streams this does not imply duration = count/rate.
:frameRateNumerator a owl:DatatypeProperty ; rdfs:label "frame rate numerator" ; rdfs:isDefinedBy <https://hexplain.io/ns/video> ; rdfs:range xsd:positiveInteger ; rdfs:comment "Numerator of the exact nominal frame rate in frames per second; used with frameRateDenominator. A decimal frameRate is a display approximation." .
:frameRateDenominator a owl:DatatypeProperty ; rdfs:label "frame rate denominator" ; rdfs:isDefinedBy <https://hexplain.io/ns/video> ; rdfs:range xsd:positiveInteger ; rdfs:comment "Positive denominator of the exact nominal frame rate, for example 1001 with numerator 30000. Both components must be supplied together." .
:RateShape a sh:NodeShape ; sh:targetSubjectsOf :frameRateNumerator, :frameRateDenominator ;
    sh:property [ sh:path :frameRateNumerator ; sh:or ( [ sh:datatype xsd:integer ] [ sh:datatype xsd:positiveInteger ] ) ; sh:minExclusive 0 ; sh:minCount 1 ; sh:maxCount 1 ] ;
    sh:property [ sh:path :frameRateDenominator ; sh:or ( [ sh:datatype xsd:integer ] [ sh:datatype xsd:positiveInteger ] ) ; sh:minExclusive 0 ; sh:minCount 1 ; sh:maxCount 1 ] .
:PositiveAspectRatioShape a sh:NodeShape ; sh:targetSubjectsOf :aspectRatio ;
    sh:sparql [ sh:message "Both aspect-ratio components must be positive." ; sh:select """
        PREFIX v: <https://hexplain.io/ns/video#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        SELECT $this WHERE {
            $this v:aspectRatio ?ratio .
            FILTER(xsd:decimal(STRBEFORE(STR(?ratio), ":")) <= 0 || xsd:decimal(STRAFTER(STR(?ratio), ":")) <= 0)
        }
    """ ] .
'''
p.write_text(s,encoding='utf-8')
p=Path('specification/aspect/time/time.ttl');s=p.read_text(encoding='utf-8')+'''
@prefix sh: <http://www.w3.org/ns/shacl#> .
:DurationShape a sh:NodeShape ; sh:targetSubjectsOf :duration ;
    sh:property [ sh:path :duration ; sh:or ( [ sh:datatype xsd:decimal ] [ sh:datatype xsd:integer ] ) ; sh:minInclusive 0 ; sh:maxCount 1 ] .
''';p.write_text(s,encoding='utf-8')
# The complete canonical graph in one normative block; remove duplicate shape blocks.
p=Path('specification/vdv/index.html');s=p.read_text(encoding='utf-8')
s=re.sub(r'(<section id="normative-owl">).*?</section>',lambda m:m[1]+'<h2>Normative vocabulary and shapes</h2><pre class="nohighlight">'+html.escape(Path('specification/vdv/video.ttl').read_text(encoding='utf-8'))+'</pre></section>',s,flags=re.S)
s=re.sub(r'<section id="normative-shacl">.*?</section>','',s,flags=re.S)
s=s.replace('<section id="properties">','''<section id="exact-timing"><h2>Exact timing</h2><p>Use <code>vdv:frameRateNumerator</code> and <code>vdv:frameRateDenominator</code> together to preserve exact nominal rates, for example 30000/1001. The denominator and numerator must be positive integers. <code>vdv:frameRate</code> is a decimal display approximation when an exact pair is present. A variable-rate stream needs per-frame timestamps; do not infer duration from nominal rate. Display aspect ratio differs from pixel aspect ratio: for square pixels it is width:height, but this equality must not be assumed for non-square pixels.</p><p><a href="video.ttl" download>Download vocabulary and SHACL</a>. From the repository root run <code>python tools/shacl_check.py your-video.ttl</code>.</p></section><section id="properties">''')
p.write_text(s,encoding='utf-8')
