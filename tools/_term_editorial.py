"""Editorial definitions for terms whose original vocabulary supplied only a label.

Existing definitions remain canonical. These annotations do not add OWL restrictions.
"""

from __future__ import annotations

DEFINITIONS: dict[str, str] = {}


def group(prefix: str, text: str) -> None:
    for line in text.strip().splitlines():
        term, definition = line.split("|", 1)
        DEFINITIONS[prefix + ":" + term] = definition


group(
    "bddo",
    "\n"
    "DataType|A reusable declaration of how a primitive field value is represented and interpreted, including "
    "its base category, width, signedness and optional RDF datatype.\n"
    "DataTypeOrStruct|The union of a primitive datatype declaration and a structured record declaration; either "
    "can supply a field's effective type.\n"
    "BaseType|The interpretation category of a primitive value before its particular width or encoding is "
    "applied.\n"
    "Endianness|The order in which the bytes of a multi-byte value contribute to its significance.\n"
    "BitOrder|The order in which bits are consumed within a byte for sub-byte fields; independent of multi-byte "
    "endianness.\n"
    "OffsetBase|The reference position against which an explicit field offset is resolved.\n"
    "Encoding|A character encoding used to convert a sequence of bytes to text.\n"
    "DataTypeRule|A conditional choice of the effective datatype or structure of a field.\n"
    "Enumeration|A mapping from raw parsed values, or bit masks when flags are enabled, to semantic symbol IRIs.\n"
    "EnumValue|One association between a raw enumeration value and the semantic symbol it denotes.\n"
    "ChecksumAlgorithm|An identifier for an integrity-check algorithm; a profile must resolve algorithm variants "
    "and parameters unambiguously.\n"
    "dataType|The primitive datatype or nested structure used to interpret a physical field when a conditional "
    "type does not replace it.\n"
    "hasConditionalDataType|The ordered list of conditional datatype rules used to select how a field is parsed.\n"
    "size|A fixed byte extent declared for a field or bounded structure. This is a byte count, not a bit width "
    "or repetition count.\n"
    "sizeFromField|A reference to an already available field whose parsed numeric value supplies the byte extent.\n"
    "sizeFromExpression|A HEL expression whose result supplies the byte extent in the applicable parsing context.\n"
    "sizeToEndOfStream|When true, consumes the remaining bytes of the applicable bounded stream region. It does "
    "not bypass an enclosing bound.\n"
    "terminator|The byte sequence that terminates a variable-length field. Delimiter handling follows the "
    "processing contract rather than an inferred text encoding.\n"
    "syncOnMarker|A byte marker used to locate synchronization points when reading a repeated structured "
    "sequence.\n"
    "encoding|The character encoding applied when interpreting a textual field.\n"
    "bitLength|The number of bits occupied by a bit-level field, distinct from a primitive datatype's declared "
    "bit width.\n"
    "bitOrder|The order used to consume bits within each byte when reading sub-byte fields; it is independent of "
    "the byte order of a multi-byte value.\n"
    "repeatCount|The fixed number of occurrences of a repeated field. Zero denotes an empty repetition.\n"
    "repeatCountFromField|The already available field whose numeric value determines a repetition count.\n"
    "repeatCountFromExpression|The HEL expression that computes the number of occurrences of a repeated field.\n"
    "repeatUntil|A HEL termination condition for a repeated field, evaluated according to the processing model's "
    "repetition rules.\n"
    "atOffset|The fixed byte displacement locating a field relative to the selected offset base.\n"
    "atOffsetFromField|The field whose parsed value supplies the byte displacement relative to the selected "
    "offset base.\n"
    "atOffsetFromExpression|A HEL expression computing a byte displacement relative to the selected offset base.\n"
    "offsetBase|The origin used to interpret a field's explicit byte displacement; it is not a spatial reference "
    "or a calibration offset.\n"
    "alignment|A positive byte-boundary requirement applied when positioning a field under the processing model.\n"
    "hasFixedValue|The literal a parsed field is required to equal, such as a signature or fixed discriminator.\n"
    "isPresentIf|A HEL boolean condition controlling whether a field occurs and consumes bytes in this instance.\n"
    "enumeration|The enumeration used to associate a field's raw value with one or more semantic symbol IRIs.\n"
    "checksum|The integrity-check declaration associated with a field, including its algorithm and covered byte "
    "interval.\n"
    "baseType|The primitive interpretation category from which a datatype is constructed.\n"
    "bitWidth|The fixed number of bits used to represent one value of a primitive datatype.\n"
    "isSigned|Whether an integer representation includes negative values. This flag does not define byte order.\n"
    "condition|The HEL Boolean expression guarding a physical parsing rule (a bddo:DataTypeRule or "
    "bddo:EndiannessRule, or a dlv:CellDataTypeRule or dlv:DimensionOrderRule): evaluated while the bytes are "
    "read, in the context of the field or struct being parsed, it decides which datatype, byte order, cell type "
    "or dimension order applies. It never chooses the RDF a node is lifted to; that is hexplain:condition.\n"
    "ruleDataType|The datatype or structure selected when a conditional datatype rule matches.\n"
    "hasEnumValue|An enumeration member associating a raw value or mask with a symbol.\n"
    "enumRawValue|The raw literal matched by an enumeration member; for flag enumerations it is interpreted as a "
    "bit mask.\n"
    "enumSymbol|The semantic resource IRI emitted for a matching enumeration member.\n"
    "checksumAlgorithm|The algorithm used to compute the integrity value over the declared coverage interval.\n"
    "coversFromField|The field whose first byte is the inclusive start of a checksum's covered interval.\n"
    "coversToField|The field whose last byte is included in a checksum's covered interval. This differs from the "
    "exclusive end used by coversToExpression.\n"
    "groupingStyle|The grouping convention that determines how opening and closing records establish named "
    "nested groups.\n"
    "BigEndian|Byte order placing the most significant byte of a multi-byte value first.\n"
    "LittleEndian|Byte order placing the least significant byte of a multi-byte value first.\n"
    "MSBFirst|Bit order consuming the most significant remaining bit of each byte first.\n"
    "LSBFirst|Bit order consuming the least significant remaining bit of each byte first.\n"
    "baseInteger|Primitive category for integral numeric values, before width and signedness are applied.\n"
    "baseFloat|Primitive category for floating-point numeric values, before a particular width is selected.\n"
    "baseString|Primitive category for textual values interpreted using a character encoding.\n"
    "baseBytes|Primitive category for an uninterpreted byte sequence.\n"
    "streamStart|Offset reference at the beginning of the applicable bounded stream.\n"
    "streamEnd|Offset reference at the end of the applicable bounded stream; interpretation follows the offset "
    "rules of the processing model.\n"
    "parentStart|Offset reference at the beginning of the containing parsed structure.\n"
    "currentPosition|Offset reference at the parser's current position before the explicitly addressed field is "
    "read.\n"
    "utf8|UTF-8 character encoding for textual bytes; a variable number of bytes may represent one Unicode "
    "scalar value.\n"
    "ascii|US-ASCII character encoding using seven-bit character values.\n"
    "utf16le|UTF-16 character encoding with each 16-bit code unit stored in little-endian byte order.\n"
    "utf16be|UTF-16 character encoding with each 16-bit code unit stored in big-endian byte order.\n"
    "latin1|ISO-8859-1 character encoding mapping each byte to the corresponding Latin-1 character value.\n"
    "bytes|Variable-length primitive byte-sequence datatype; its extent is supplied by the field's sizing "
    "mechanism.\n"
    "string|Variable-length primitive text datatype; its byte extent and character encoding are supplied by the "
    "field/profile.\n"
    "DispatchTable|A keyed, open selection of a field's effective type: the dispatch key is matched by equality "
    "against the keys of arms that any importing description may contribute.\n"
    "DispatchArm|One key-to-type association contributed to a dispatch table; keys are unique within a table "
    "across all contributing graphs.\n"
    "SeekScope|The reach of an offset-addressed read: the innermost bounded region, or the whole stream.\n"
    "hasDispatchTable|The keyed dispatch table that selects this field's effective type; exclusive with the "
    "ordered conditional datatype rules.\n"
    "dispatchOnField|The sibling field whose parsed value is the dispatch key.\n"
    "dispatchOnExpression|A HEL expression whose value is the dispatch key.\n"
    "dispatchDefault|The type selected when no arm matches the dispatch key.\n"
    "armTable|The dispatch table an arm contributes to.\n"
    "armKey|The string or integer key value an arm matches by equality.\n"
    "armDataType|The datatype or structure selected when an arm's key matches.\n"
    "seekScope|Whether an offset-addressed read is confined to its bounded region or resolved against the whole "
    "stream.\n"
    "regionScope|Seek scope confining an offset-addressed read to the innermost bounded region; the default.\n"
    "streamScope|Seek scope resolving an offset-addressed read against the whole stream, suspending the region "
    "bound for that read.\n",
)
group(
    "dlv",
    "\n"
    "DataLayout|A declaration of how logical array cells are addressed in a physical byte region, including "
    "dimensions, strides, cell type and optional chunking.\n"
    "Dimension|One position in a data layout's ordered dimensions, with an extent, optional stride or chunk "
    "size, and optional axis meaning.\n"
    "Axis|The logical meaning of a dimension, independent of the dimension's extent or storage stride.\n"
    "dimensionSize|The fixed number of cells along a physical-layout dimension.\n"
    "dimensionSizeFromField|The field whose parsed value supplies a layout dimension's extent.\n"
    "cellDataType|The datatype of a single array cell before any conditional cell-type rule is applied.\n"
    "ruleCellDataType|The cell datatype selected when the associated conditional rule matches.\n"
    "chunkSizeFromField|The field whose parsed value supplies the number of cells per chunk along a dimension.\n"
    "hasAxis|The logical axis assigned to a physical-layout dimension; it does not itself establish byte order.\n"
    "axisX|The logical horizontal or first spatial coordinate axis of a layout.\n"
    "axisY|The logical vertical-in-grid or second spatial coordinate axis of a layout; ground-coordinate "
    "direction is specified separately.\n"
    "axisZ|The third spatial coordinate axis of a layout.\n"
    "axisTime|The temporal axis of a layout; sample spacing and time reference must be described separately.\n"
    "axisBand|The axis indexing separate bands or channels of a multi-component array.\n"
    "rowMajor|Chunk enumeration convention in which the last logical dimension varies fastest.\n"
    "columnMajor|Chunk enumeration convention in which the first logical dimension varies fastest.\n"
    "morton|Chunk traversal in ascending Morton (Z-order) key, constructed as the term's comment specifies.\n"
    "hilbert|Chunk traversal in ascending Hilbert-curve key, constructed as the term's comment specifies.\n",
)
group(
    "hexplain",
    "\n"
    "forProperty|The semantic RDF predicate whose controlled-value register binding is declared by this binding "
    "resource.\n"
    "codecParameter|A named parameter value associated with one stage of an encoding pipeline.\n"
    "hasConditionalMapping|An ordered list of mapping rules that choose a semantic property according to the "
    "parsed instance.\n"
    "condition|The HEL Boolean expression guarding a semantic mapping rule (a hexplain:MappingRule or "
    "hexplain:ClassMappingRule): evaluated after the bytes are parsed, in the context of the field or struct "
    "being lifted, it decides which property or class the lifted RDF uses. It never changes how bytes are read; "
    "that is bddo:condition.\n"
    "semanticProperty|The RDF property selected by a matching semantic mapping rule.\n",
)
group(
    "gv",
    "\n"
    "axisLatitude|Deprecated duplicate of dlv:axisY, kept so existing descriptions resolve. Geographic meaning "
    "of a grid axis comes from its spatial reference, not from a separate axis individual.\n"
    "axisLongitude|Deprecated duplicate of dlv:axisX, kept so existing descriptions resolve. Geographic meaning "
    "of a grid axis comes from its spatial reference, not from a separate axis individual.\n"
    "axisElevation|Deprecated duplicate of dlv:axisZ, kept so existing descriptions resolve. Units and vertical "
    "reference are supplied by the spatial reference.\n"
    "axisPoint|The index axis of an unstructured point sequence, rather than a regular spatial grid direction.\n"
    "RasterDataset|A georeferenced dataset whose values are organized as sample grids or raster bands, described "
    "using raster and spatial-reference aspects.\n"
    "VectorDataset|A georeferenced dataset whose spatial content is represented by explicit geometries and "
    "associated attributes.\n"
    "PointCloud|A georeferenced collection of sampled points with per-point positions and optional attributes, "
    "without assuming a regular grid.\n",
)
group(
    "img",
    "\n"
    "Image|A raster image considered as a semantic resource, with sample dimensions and interpretation supplied "
    "by the imported aspects.\n"
    "ImageHeader|A structural component carrying metadata needed to interpret a raster image, separate from its "
    "pixel payload.\n"
    "ColorProfile|A resource describing the color interpretation associated with image samples; its concrete "
    "representation is format-specific.\n"
    "PixelData|The image component containing encoded or decoded sample values, distinct from header metadata.\n"
    "colorType|The legacy integer color-type code carried by an image header. In this vocabulary it preserves a "
    "PNG-oriented wire code, not a universal color-space identifier.\n"
    "compressionMethod|The legacy integer compression-method code carried by an image header; the code's "
    "interpretation is profile-specific.\n"
    "filterMethod|The legacy integer filtering-method code carried by an image header; it does not name a "
    "general-purpose semantic filter.\n"
    "interlaceMethod|The legacy integer interlacing-method code carried by an image header; decode its meaning "
    "using the format profile.\n",
)
group(
    "adv",
    """
AudioContainer|A containing resource for encoded audio content and associated tracks or metadata.
AudioStream|An ordered audio sample stream whose sampling, channel and encoding properties are described separately.
MetadataTag|A metadata-bearing component carrying descriptive information about an audio work or recording.
artist|The artist credit as text supplied by the source metadata; it is not an identified person resource.
album|The album or collection title as text supplied by the source metadata.
trackTitle|The title of the audio track as supplied by the source metadata.
genre|The genre label as supplied by the source; no universal genre classification scheme is implied.
trackNumber|The source's integer ordinal identifying a track within its collection.
axisSample|Deprecated duplicate of dlv:axisTime for successive audio samples, kept so existing descriptions resolve.
axisChannel|Deprecated duplicate of dlv:axisBand for audio channels, kept so existing descriptions resolve.
""",
)
group(
    "vdv",
    "\n"
    "VideoContainer|A containing resource for one or more video streams and associated tracks or metadata.\n"
    "VideoStream|An ordered video sequence with timing and display properties independent of its container "
    "encoding.\n"
    "VideoTrack|A container-level track carrying a video sequence; track identity is distinct from individual "
    "frames.\n"
    "frameRate|The nominal number of frames per second expressed as a decimal or integer value. Exact "
    "non-terminating rational rates require the numerator/denominator properties.\n"
    "frameCount|The declared number of frames in a video sequence; it does not by itself establish duration for "
    "variable-rate material.\n"
    "audioChannels|The declared number of audio channels associated with the video resource.\n"
    "scanType|The scanning convention used to organize image lines into frames or fields.\n"
    "Progressive|Scanning convention in which a frame represents a full image rather than alternating interlaced "
    "fields.\n"
    "Interlaced|Scanning convention in which successive fields carry different line subsets of an image frame.\n"
    "axisFrame|Deprecated duplicate of dlv:axisTime for successive video frames, kept so existing descriptions "
    "resolve.\n",
)
group(
    "axv",
    "\n"
    "Archive|A container resource packaging independently identifiable member entries.\n"
    "ArchiveEntry|One member of an archive, including its payload and associated entry metadata.\n"
    "CentralDirectory|An index component describing archive entries and the information needed to locate them.\n"
    "compressedSize|The number of bytes occupied by an archive entry's compressed representation, distinct from "
    "its logical uncompressed size.\n"
    "entryComment|Free-text commentary associated with an individual archive entry.\n",
)
group(
    "dfv",
    "\n"
    "Document|A document resource composed of content, structural objects and metadata, rather than a particular "
    "byte serialization.\n"
    "Page|One page in a paginated document.\n"
    "Object|An addressable internal document object whose concrete type and storage are determined by the "
    "document format.\n"
    "Stream|A document object containing a sequence of content bytes, possibly encoded.\n"
    "CrossReferenceTable|A document index relating object identities to their stored locations or resolution "
    "information.\n"
    "Trailer|A closing document structure carrying references or metadata needed to resolve the document's "
    "logical root.\n"
    "Font|A typeface resource providing glyph representations and metrics.\n"
    "FontDescriptor|A metadata component describing a font's identity, characteristics or metrics.\n"
    "FontTable|A typed table within a structured font representation.\n"
    "Glyph|One graphical shape used in rendering text; glyph identity need not equal a Unicode character value.\n"
    "BoundingBox|A rectangular boundary associated with a page, glyph or other document component; coordinate "
    "conventions come from the owning profile.\n"
    "pageCount|The declared number of pages in a document.\n"
    "creatorTool|The source-reported software tool used to author the document content.\n"
    "producerTool|The source-reported software tool used to produce the stored document representation.\n"
    "fontFamily|The family name identifying a related set of font faces.\n"
    "fontStyle|The source's style description for a font face, such as weight or slant designation.\n"
    "glyphCount|The number of glyph entries declared by a font resource.\n"
    "glyphIdentifier|The source-local identifier of a glyph; no global character identity is implied.\n"
    "unicodeCodePoint|The Unicode scalar/code-point value associated with a glyph mapping; it is distinct from a "
    "font-local glyph index.\n"
    "characterEncoding|The source's designation of the character-to-glyph encoding used by a font or text "
    "component.\n"
    "hasBoundingBox|The bounding-box resource associated with a document, page or glyph component.\n"
    "boxType|The source's designation of the kind of bounding box, whose semantics and coordinates are specified "
    "by the document profile.\n",
)
group(
    "npv",
    "\n"
    "Packet|A protocol data unit represented as a semantic network resource; protocol-specific interpretation is "
    "supplied by its type and profile.\n"
    "EthernetFrame|A link-layer frame represented according to an Ethernet format profile.\n"
    "IPv4Packet|A network-layer packet represented according to an Internet Protocol version 4 profile.\n"
    "IPv6Packet|A network-layer packet represented according to an Internet Protocol version 6 profile.\n"
    "TCPSegment|A transport-layer protocol data unit represented according to a TCP profile.\n"
    "UDPDatagram|A transport-layer protocol data unit represented according to a UDP profile.\n",
)
group(
    "anet",
    "\n"
    "sourceAddress|The sender address as text in the notation selected by the protocol profile.\n"
    "destinationAddress|The recipient address as text in the notation selected by the protocol profile.\n"
    "sourcePort|The transport endpoint number carried for the sender; protocol meaning and allowed values come "
    "from the profile and applicable shapes.\n"
    "destinationPort|The transport endpoint number carried for the recipient; protocol meaning and allowed "
    "values come from the profile and applicable shapes.\n"
    "etherType|The link-layer type discriminator identifying the interpretation of the encapsulated payload.\n"
    "protocolNumber|The network-layer protocol discriminator identifying the encapsulated transport or next "
    "protocol.\n"
    "sequenceNumber|The source protocol's sequence position or identifier; interpretation and wrap behavior are "
    "protocol-specific.\n"
    "acknowledgmentNumber|The source protocol's acknowledgment position or identifier, interpreted in the "
    "applicable sequence space.\n"
    "tcpFlags|The raw TCP control-bit pattern represented as hexadecimal binary data; individual flag meanings "
    "come from the TCP profile.\n",
)
group(
    "afs",
    "\n"
    "fileName|The name of a file or directory entry as recorded by its container or filesystem representation.\n"
    "isDirectory|Whether an entry denotes a directory rather than a regular file payload.\n"
    "creationTime|The source-reported time at which an entry was created; precision and timezone availability "
    "depend on the format.\n"
    "modificationTime|The source-reported time at which an entry's content was last modified.\n",
)
group(
    "aprov",
    """
AcquisitionInfo|A metadata resource describing the acquisition of data, including its time and observing equipment.
SensorModel|A resource identifying or describing the instrument or sensor model responsible for observations.
Platform|A resource identifying the carrier or platform on which an observing sensor operates.
acquisitionTime|The time associated with acquiring the data, distinct from file creation time or coordinate epoch.
platformName|The source-reported textual name of the observing platform.
sensorType|The source-reported textual designation of the observing sensor or sensor type.
""",
)
group(
    "abnd",
    "\n"
    "hasPart|A member resource belonging to a compound asset; the relation represents logical membership, not a "
    "byte offset.\n"
    "partOf|The asset of which a part is a logical member.\n"
    "boundBy|The binding convention used to associate a member with its asset, selected from the declared "
    "BindingKind individuals.\n"
    "partSpec|A part specification declared by a bundle profile, describing a role and its structural or "
    "discovery expectations.\n"
    "required|Whether the part described by a part specification is required by the bundle contract.\n",
)
group(
    "araster",
    "\n"
    "hasBand|A band view belonging to a raster grid. A reused physical sample plane may need distinct band views "
    "when its position differs between grids.\n"
    "hasArray|A logical array contained in a group, independent of its physical storage path.\n"
    "hasGroup|A logical child group within an acyclic array-group hierarchy.\n"
    "dimensionName|The source-level name of a logical array dimension, independent of its position in any one "
    "array.\n",
)
group(
    "asref",
    "\n"
    "CoordinateReferenceSystem|A resource describing the coordinate system and reference frame in which spatial "
    "coordinates are interpreted.\n"
    "epsgCode|The positive numeric code identifying a coordinate reference system in the EPSG registry; it is "
    "not a complete substitute for all CRS metadata.\n"
    "hasGeoTransform|The complete affine transformation resource relating grid column/row coordinates to ground "
    "coordinates.\n"
    "hasGroundControlPoint|A measured or supplied correspondence between an image-grid location and a ground "
    "coordinate.\n"
    "hasRationalTransform|The rational-polynomial geolocation model associated with a resource, with its basis "
    "contract declared explicitly.\n"
    "gcpX|The first ground-coordinate ordinate of a control point in the declared control-point CRS.\n"
    "gcpY|The second ground-coordinate ordinate of a control point in the declared control-point CRS.\n"
    "gcpIdentifier|The source-local identifier distinguishing a control point within its control-point set.\n"
    "pixelRegistration|Where a cell's value is located within the cell: at its centre (asref:PixelCenter, a "
    "point sample) or representing the cell from its upper-left corner (asref:PixelCorner, an area value). It "
    "describes the value, not the grid: the normalized affine (asref:GeoTransform) is always corner-based, so "
    "this property never shifts the affine or the column and row of a world point.\n"
    "PixelCorner|Registration of a cell's value at, or as an area from, the cell's upper-left corner. The "
    "normalized affine is corner-based whatever the registration: column/row (0, 0) is the outer corner of the "
    "first cell.\n"
    "PixelCenter|Registration of a cell's value at the centre of its cell (a point sample, such as an elevation "
    "post). It does not move the grid: the normalized affine stays corner-based, and a source whose native "
    "transform is centre-based is shifted by half a cell when it is normalized, once, at lifting time.\n",
)
group(
    "asamp",
    """
SignedInteger|Sample interpretation admitting negative and nonnegative integral values; precision is stated separately.
UnsignedInteger|Sample interpretation admitting only nonnegative integral values; precision is stated separately.
Float|Sample interpretation using floating-point numeric values rather than integer quantization codes.
""",
)
group(
    "atab",
    "\n"
    "rowCount|The declared number of records in a tabular resource, including zero for an empty table.\n"
    "hasField|A typed column declaration belonging to the table's schema.\n"
    "fieldName|The source-level name identifying a column within its table schema.\n"
    "fieldDataType|The source's textual datatype designation for a column; a format profile defines how this "
    "name is interpreted.\n",
)
group(
    "apkg",
    "\n"
    "Entry|An individually identifiable member of a packaging container, with membership and content metadata "
    "described separately.\n"
    "hasEntry|A member entry contained in a packaging resource; the relation does not by itself prescribe the "
    "member's encoding.\n",
)

group(
    "asig",
    "\n"
    "sampleRate|The number of sample instants per second for a sampled signal, expressed in hertz. Channel count "
    "is separate; a multi-channel sample instant is not multiplied by its number of channels.\n",
)

group(
    "atime",
    "\n"
    "duration|The elapsed playing time of content expressed in seconds. It is a temporal extent, distinct from a "
    "timestamp or a count of frames or samples.\n",
)
group(
    "apc",
    """
pointCount|The declared number of points in an unstructured point collection, including zero for an empty collection.
""",
)
group(
    "rpr",
    "\n"
    "Payload|A member carrying the principal data values or encoded content of a compound asset.\n"
    "Metadata|A member carrying descriptive information about another member or the asset as a whole.\n"
    "SpatialReference|A member carrying coordinate-reference or georeferencing information needed to interpret "
    "spatial content.\n"
    "AttributeTable|A member carrying non-geometric records or attributes associated with the asset's features.\n"
    "GeometryCarrier|A member carrying the explicit geometries associated with the asset's features.\n"
    "SpatialIndex|A member carrying an index for locating spatial content efficiently; it is distinct from the "
    "content itself.\n"
    "CharacterEncoding|A member identifying how textual bytes in the asset are decoded into characters.\n"
    "Checksum|A member carrying integrity values used to check one or more other members.\n"
    "Thumbnail|A member carrying a reduced preview intended for visual recognition of the asset.\n"
    "Manifest|A member identifying the asset's constituent members and their organization or references.\n"
    "Sidecar|An accompanying member associated with a primary resource by the bundle's binding convention.\n"
    "Segment|One ordered portion of an asset distributed across multiple members.\n",
)
group(
    "rgeo",
    """
Point|A geometry consisting of a single coordinate position.
LineString|A geometry consisting of an ordered sequence of positions joined by line segments.
Polygon|A planar surface geometry bounded by an exterior ring and optionally interior rings.
MultiPoint|A geometry collection whose members are points.
MultiLineString|A geometry collection whose members are line strings.
MultiPolygon|A geometry collection whose members are polygons.
""",
)
group(
    "menc",
    "\n"
    "H264|Identifier for the H.264/AVC video coding family. Profiles must identify applicable bitstream framing "
    "and configuration.\n"
    "HEVC|Identifier for the H.265/HEVC video coding family. Container framing is specified separately.\n"
    "ProRes|Identifier for the ProRes video coding family; the concrete variant belongs to the format/profile "
    "metadata.\n"
    "AV1|Identifier for the AV1 video coding format; container and configuration details remain separate.\n"
    "VP9|Identifier for the VP9 video coding format; container framing remains separate.\n"
    "AAC|Identifier for the Advanced Audio Coding family; profiles specify the object type and framing when "
    "required.\n"
    "MP3|Identifier for MPEG audio Layer III coded audio, distinct from a file's metadata-tag container.\n"
    "FLAC|Identifier for Free Lossless Audio Codec data, whose purpose is lossless audio representation.\n"
    "Opus|Identifier for Opus coded audio; transport/container framing is not implied by this concept alone.\n"
    "PCM|Identifier for linearly quantized pulse-code-modulated samples; width, signedness, channel organization "
    "and byte order must be specified separately.\n"
    "Store|Identity encoding: bytes are stored without a compression transform.\n"
    "Deflate|Identifier for the DEFLATE compression format. A gzip or zlib wrapper must not be inferred from "
    "this identifier alone.\n"
    "Gzip|Identifier for gzip-framed compressed data, distinct from an unwrapped DEFLATE bitstream.\n"
    "BZip2|Identifier for bzip2 compressed data; the profile must identify framing and relevant options when "
    "they affect interpretation.\n"
    "LZMA|Identifier for the LZMA compression family; framing, dictionary and variant information must be "
    "supplied where required.\n"
    "Zstd|Identifier for data in the Zstandard frame format (one or more concatenated frames); dictionary "
    "requirements belong to the profile.\n"
    "Snappy|Identifier for Snappy compression; raw versus framed representation must be determined by the "
    "profile.\n"
    "LZ4|Identifier for data in the LZ4 Frame format, the self-describing framed representation of LZ4 "
    "compression; the raw block representation is menc:LZ4Block.\n"
    "LZ4Block|Identifier for a single raw LZ4 compressed block, which carries no length of its own: the decoded "
    "size must be supplied by the profile.\n"
    "RunLength|An encoding that represents repeated values as runs; the profile must identify the actual "
    "run/count representation.\n"
    "Blosc|Identifier for the Blosc compression framework, which combines an inner compressor with configurable "
    "preprocessing and block settings.\n"
    "Delta|A predictive transform that represents values by differences from preceding or predicted values; the "
    "variant and arithmetic are profile parameters.\n"
    "Shuffle|A reversible transform grouping corresponding bytes of successive fixed-width values to prepare "
    "them for compression.\n"
    "BitShuffle|A reversible transform grouping corresponding bits of successive values to prepare them for "
    "compression; element/block parameters belong to the profile.\n",
)
group(
    "rcol",
    "\n"
    "sRGB|Identifier for the sRGB color-space convention. Channel coding and embedding of any color profile "
    "remain format-specific.\n"
    "BT601|Identifier for color interpretation associated with the BT.601 television-system convention; the "
    "profile must supply the applicable variant and signal range.\n"
    "BT709|Identifier for color interpretation associated with the BT.709 high-definition television convention; "
    "transfer and range details must be retained by the profile.\n"
    "BT2020|Identifier for color interpretation associated with the BT.2020 ultra-high-definition television "
    "convention; this does not by itself choose an HDR transfer function.\n",
)
ALGORITHMS = {
    "crc16": "The CRC-16/CCITT-FALSE integrity check: polynomial 0x1021, initial value 0xFFFF, no input or output "
    "reflection and final XOR 0x0000 (check value 0x29B1 over the ASCII bytes 123456789). Other CRC-16 variants, "
    "such as CRC-16/ARC or CRC-16/XMODEM, have identifiers of their own.",
    "crc32": "The CRC-32/ISO-HDLC integrity check used by zlib and PNG: reflected polynomial 0xEDB88320, initial value "
    "0xFFFFFFFF and final XOR 0xFFFFFFFF (check value 0xCBF43926 over the ASCII bytes 123456789). Other 32-bit "
    "CRC variants, such as CRC-32C, have identifiers of their own.",
    "crc8Smbus": "The CRC-8/SMBUS integrity check: width 8, polynomial 0x07, initial value 0x00, no input or output "
    "reflection and final XOR 0x00 (check value 0xF4 over the ASCII bytes 123456789).",
    "crc16Arc": "The CRC-16/ARC integrity check: width 16, polynomial 0x8005, initial value 0x0000, input and output "
    "reflected and final XOR 0x0000 (check value 0xBB3D over the ASCII bytes 123456789).",
    "crc16Xmodem": "The CRC-16/XMODEM integrity check: width 16, polynomial 0x1021, initial value 0x0000, no "
    "input or output "
    "reflection and final XOR 0x0000 (check value 0x31C3 over the ASCII bytes 123456789).",
    "crc16Modbus": "The CRC-16/MODBUS integrity check: width 16, polynomial 0x8005, initial value 0xFFFF, input "
    "and output "
    "reflected and final XOR 0x0000 (check value 0x4B37 over the ASCII bytes 123456789).",
    "crc16X25": "The CRC-16/IBM-SDLC (X-25) integrity check: width 16, polynomial 0x1021, initial value 0xFFFF, "
    "input and "
    "output reflected and final XOR 0xFFFF (check value 0x906E over the ASCII bytes 123456789).",
    "crc32c": "The CRC-32/ISCSI (CRC-32C) integrity check: width 32, polynomial 0x1EDC6F41, initial value 0xFFFFFFFF, "
    "input and output reflected and final XOR 0xFFFFFFFF (check value 0xE3069283 over the ASCII bytes 123456789).",
    "crc32Bzip2": "The CRC-32/BZIP2 integrity check: width 32, polynomial 0x04C11DB7, initial value 0xFFFFFFFF, "
    "no input or "
    "output reflection and final XOR 0xFFFFFFFF (check value 0xFC891918 over the ASCII bytes 123456789).",
    "crc32Mpeg2": "The CRC-32/MPEG-2 integrity check: width 32, polynomial 0x04C11DB7, initial value 0xFFFFFFFF, "
    "no input or "
    "output reflection and final XOR 0x00000000 (check value 0x0376E6E7 over the ASCII bytes 123456789).",
    "crc64Ecma182": "The CRC-64/ECMA-182 integrity check: width 64, polynomial 0x42F0E1EBA9EA3693, initial value "
    "0x0000000000000000, no input or output reflection and final XOR 0x0000000000000000 (check value "
    "0x6C40DF5F0B497347 over the ASCII bytes 123456789).",
    "crc64Xz": "The CRC-64/XZ integrity check: width 64, polynomial 0x42F0E1EBA9EA3693, initial value "
    "0xFFFFFFFFFFFFFFFF, "
    "input and output reflected and final XOR 0xFFFFFFFFFFFFFFFF (check value 0x995DC9BBDF1939FA over the ASCII "
    "bytes 123456789).",
    "adler32": "The Adler-32 checksum identifier, producing a 32-bit integrity value for a byte sequence.",
    "md5": "The MD5 message-digest identifier, producing a 128-bit digest; this term identifies a stored integrity "
    "algorithm and does not claim cryptographic security.",
    "sha1": "The SHA-1 message-digest identifier, producing a 160-bit digest; this term does not claim suitability for "
    "collision-resistant security uses.",
    "sha256": "The SHA-256 message-digest identifier, producing a 256-bit digest of the covered byte sequence.",
}
for term, definition in ALGORITHMS.items():
    DEFINITIONS["bddo:" + term] = definition
for term, key in [
    ("CRC16", "crc16"),
    ("CRC32", "crc32"),
    ("Adler32", "adler32"),
    ("MD5", "md5"),
    ("SHA1", "sha1"),
    ("SHA256", "sha256"),
    ("CRC8SMBus", "crc8Smbus"),
    ("CRC16ARC", "crc16Arc"),
    ("CRC16XMODEM", "crc16Xmodem"),
    ("CRC16MODBUS", "crc16Modbus"),
    ("CRC16X25", "crc16X25"),
    ("CRC32C", "crc32c"),
    ("CRC32BZIP2", "crc32Bzip2"),
    ("CRC32MPEG2", "crc32Mpeg2"),
    ("CRC64ECMA182", "crc64Ecma182"),
    ("CRC64XZ", "crc64Xz"),
]:
    DEFINITIONS["rck:" + term] = ALGORITHMS[key]

# Term-specific usage notes (skos:scopeNote). A term listed here gets exactly this note; a term of
# a module in _reference.TERM_SCOPED that is not listed and states no note of its own gets only
# the sentences that are true of it. The module sentence of _reference.SCOPE is NOT prefixed to
# these: "Use when linking a physical format description to semantic RDF output" was wrong for
# hexplain:RegisterStatus, hexplain:status and hexplain:correspondsTo, which concern registers.
SCOPE_NOTES: dict[str, str] = {}


def notes(prefix: str, text: str) -> None:
    for line in text.strip().splitlines():
        term, note = line.split("|", 1)
        SCOPE_NOTES[prefix + ":" + term] = note


notes(
    "hexplain",
    "\n"
    "ClassMappingRule|Assert on each member of a hexplain:hasConditionalClassMapping list, with one hexplain:condition "
    "and one hexplain:semanticClass. Rules are tried in list order; the first whose condition holds decides the "
    "struct's class.\n"
    "CodecParameter|Assert on each object of hexplain:codecParameter, with exactly one hexplain:parameterName, spelt "
    "as the codec itself names the setting, and exactly one of hexplain:parameterValue or hexplain:parameterExpression "
    "as its value.\n"
    "EncodingStep|Assert on each member of a hexplain:hasEncodingStep list, naming its codec with exactly one "
    "hexplain:codec, or selecting it at run time with hexplain:codecFromExpression and hexplain:codecCandidates "
    "instead, plus any hexplain:codecParameter settings a codec-naming step was applied with (a selecting step carries "
    "none of its own). List the steps in the order the encoder applied them.\n"
    "MappingRule|Assert on each member of a hexplain:hasConditionalMapping list, with one hexplain:condition and one "
    "hexplain:semanticProperty, and optionally a hexplain:valueExpression computing the value that arm emits.\n"
    "RegisterBinding|Assert on the object of each hexplain:usesRegister, with exactly one hexplain:forProperty and one "
    "hexplain:register. Several bindings for one property are read together: a value in any of their schemes is "
    "accepted.\n"
    "RegisterStatus|The class of the three controlled values of hexplain:status; do not mint further statuses. A "
    "register publishes the status of its entries; data never states it.\n"
    "byteLength|Stated by a processor on the resources it lifts, with hexplain:byteOffset, when it records byte "
    "ranges; a profile does not declare it. Also locates a conf:Finding's evidence.\n"
    "byteOffset|Stated by a processor on the resources it lifts, with hexplain:byteLength, when it records byte "
    "ranges; a profile does not declare it. Also locates a conf:Finding's evidence.\n"
    "codec|Use at most once on a hexplain:EncodingStep, naming a concept of the codec or compression register the "
    "profile binds; mutually exclusive with hexplain:codecFromExpression, which selects the codec at run time "
    "instead.\n"
    "codecParameter|Use on a hexplain:EncodingStep, once per setting the codec was applied with; omit it for a codec "
    "that takes none, and for a step that selects its codec at run time with hexplain:codecFromExpression (its "
    "hexplain:codecCandidates carry the parameters instead).\n"
    "condition|Use exactly once on a hexplain:MappingRule or hexplain:ClassMappingRule: a HEL Boolean expression "
    "evaluated in the context of the field or struct being mapped.\n"
    "correspondsTo|Use on a register concept to name the ontology individual that denotes the same thing in another "
    "layer (a checksum concept and its bddo:ChecksumAlgorithm). It is an annotation: never a SKOS mapping, never "
    "equivalence, and it licenses no inference.\n"
    "forProperty|Use exactly once on a hexplain:RegisterBinding, naming the property whose values the binding "
    "constrains.\n"
    "hasConditionalClassMapping|Use at most once on a bddo:Struct whose class depends on a discriminator; its object "
    "is an rdf:List of hexplain:ClassMappingRule. Do not combine with hexplain:mapsToClass on the same struct.\n"
    "hasConditionalMapping|Use at most once on a bddo:Field whose meaning depends on a discriminator; its object is an "
    "rdf:List of hexplain:MappingRule, the first matching rule deciding the property and value emitted.\n"
    "hasDataLayout|Use at most once on a bddo:Field whose bytes are a multi-dimensional array, naming the "
    "dlv:DataLayout that addresses its cells.\n"
    "hasEncodingStep|Use at most once on a bddo:Field whose bytes pass through a pipeline of codecs; its object is an "
    "rdf:List of hexplain:EncodingStep in encoding order. Do not combine with hexplain:isEncodedWith.\n"
    "isEncodedWith|Use at most once on a bddo:Field whose bytes are encoded by a single codec without parameters. For "
    "several codecs or parameterised ones, use hexplain:hasEncodingStep instead.\n"
    "language|Use at most once on a bddo:Field that emits a string literal, with a BCP 47 tag fixed by the format. Do "
    "not combine with hexplain:languageFromField.\n"
    "languageFromField|Use at most once on a bddo:Field whose language the data states in a sibling field, naming that "
    "field. Do not combine with hexplain:language.\n"
    "mapsToClass|Use at most once on a bddo:Struct, naming the owl:Class every parsed instance of it is typed with. "
    "Use hexplain:hasConditionalClassMapping when the class depends on a discriminator.\n"
    "mapsToObjectProperty|Use at most once on a bddo:Field whose emitted object is an IRI: a nested struct's resource "
    "or an enumeration symbol. Use hexplain:mapsToProperty for a literal value.\n"
    "mapsToProperty|Use on a bddo:Field that emits a literal, naming the property the literal is the value of.\n"
    "parameterName|Use exactly once on a hexplain:CodecParameter.\n"
    "parameterValue|Use on a hexplain:CodecParameter that is not given a hexplain:parameterExpression instead, as the "
    "literal the format carries, with the datatype that literal naturally has.\n"
    "register|Use exactly once on a hexplain:RegisterBinding, naming the skos:ConceptScheme whose members are "
    "permitted values of the bound property.\n"
    "semanticClass|Use exactly once on a hexplain:ClassMappingRule, naming the class chosen when its condition holds.\n"
    "semanticProperty|Use exactly once on a hexplain:MappingRule, naming the property emitted when its condition "
    "holds.\n"
    "status|Use at most once on a register entry (a concept, collection or scheme) that a register retires or "
    "reaffirms. A deprecated or superseded entry is also owl:deprecated true and has a history note; a superseded one "
    "names its replacement with dcterms:isReplacedBy.\n"
    "statusDeprecated|Use as the hexplain:status of a retired register entry that has no single replacement.\n"
    "statusSuperseded|Use as the hexplain:status of a retired register entry that names its replacement with "
    "dcterms:isReplacedBy.\n"
    "statusValid|Use as the hexplain:status of a current register entry, where saying so explicitly helps; an entry "
    "with no status is current unless it is owl:deprecated.\n"
    "unit|Use at most once on a bddo:Field whose value is a quantity, naming its unit of measure. It records the unit; "
    "it does not rescale the value.\n"
    "usesRegister|Use on the profile, once per property it binds to a register; the object is a "
    "hexplain:RegisterBinding.\n"
    "valueDatatype|Use at most once beside a hexplain:valueExpression, naming the datatype of the literal it emits "
    "when the HEL result's natural datatype is not the one wanted.\n"
    "valueExpression|Use at most once on a bddo:Field or a hexplain:MappingRule, when the emitted value is computed "
    "from the parsed one (scaling, offsets, unit conversion) rather than copied.\n",
)

notes(
    "abnd",
    "\n"
    "Asset|Assert on the IRI of one logical asset a Bundle Processor assembled from its parts; it is linked to "
    "its profile by dcterms:conformsTo and carries the facets lifted from its parts.\n"
    "BindingKind|The class of the four controlled values of abnd:boundBy; do not mint further kinds.\n"
    "BundleProfile|Assert on a reusable description of a multi-part format: its abnd:partSpec members and, "
    "optionally, its abnd:boundBy kind.\n"
    "Concatenation|Use as the abnd:boundBy of an asset whose parts are consecutive fragments of one byte stream, "
    "ordered by abnd:partIndex.\n"
    "Containment|Use as the abnd:boundBy of an asset whose parts are members of one container stream (a ZIP or "
    "TAR archive).\n"
    "ManifestReference|Use as the abnd:boundBy of an asset whose primary part names its other members by path or "
    "IRI.\n"
    "NamingConvention|Use as the abnd:boundBy of an asset whose members are sibling files sharing a stem, one "
    "role per extension.\n"
    "Part|Assert on each part root a Bundle Processor lifts; it carries its spec's abnd:partRole and the facet "
    "properties parsed from the part.\n"
    "PartSpec|Assert on each object of abnd:partSpec: one expected member, located by abnd:extension or "
    "abnd:pathPattern, with a role and optionally its struct, count bounds and carried aspect.\n"
    "boundBy|Use at most once on an abnd:Asset or abnd:BundleProfile, with one of the four abnd:BindingKind "
    "values.\n"
    "carriesAspect|Use on an abnd:PartSpec to name the aspect ontology whose properties the part contributes to "
    "the asset. It is not an owl:imports.\n"
    "describedBy|Use at most once on an abnd:PartSpec, naming the bddo:Struct that parses the member. The "
    "struct's local name is the part's name in HEL (asset.Name), so no two specs of one profile may use structs "
    "with the same local name.\n"
    "extension|Use on an abnd:PartSpec to locate a member at the asset root by its file-name ending, a dot and "
    'one or more steps (".dbf", ".tar.gz"). Several values are alternatives. Do not combine with '
    "abnd:pathPattern.\n"
    "hasPart|Use on an abnd:Asset, once per part root it was assembled from.\n"
    "liftsProperty|Use on an abnd:PartSpec, once per property of the carried aspect the asset receives from the "
    "part, by IRI. Listing the properties is recommended: without a list, every property the aspect defines is "
    "lifted.\n"
    "maxParts|Use at most once on an abnd:PartSpec when a member may match more than one file; absent means one "
    "for an extension and unbounded for a pattern. Never 0 on a required spec.\n"
    "minParts|Use at most once on an abnd:PartSpec that matches several files; absent means 1 when abnd:required "
    "is true and 0 otherwise. Never 0 on a required spec.\n"
    "nestedProfile|Use at most once on an abnd:PartSpec whose member is a directory with a structure of its own, "
    "naming the abnd:BundleProfile of that directory. A profile may not nest itself, directly or through other "
    "profiles.\n"
    "partIndex|Use at most once on an abnd:Part of a concatenated asset, giving its zero-based position in the "
    "byte stream.\n"
    "partOf|Use on an abnd:Part to name its asset where the data states it; a Bundle Processor does not infer it "
    "from abnd:hasPart.\n"
    "partRole|Use exactly once on an abnd:PartSpec and on each abnd:Part it matched, naming a concept of the "
    "part-role register the profile binds.\n"
    "partSpec|Use on an abnd:BundleProfile, once per expected member.\n"
    "pathPattern|Use on an abnd:PartSpec to locate a member by its path relative to the asset root: "
    "'/'-separated segments, with * within a segment, ** across segments and ? for one character, never '.', "
    "'..', a backslash or a drive letter. Several values are alternatives. Do not combine with abnd:extension.\n"
    "primary|Use at most once on an abnd:PartSpec, true for the one member that anchors recognition of the "
    "asset; a profile has at most one primary spec.\n"
    "primaryPart|Use at most once on an abnd:Asset, naming the part root matched to the primary spec.\n"
    "required|Use at most once on an abnd:PartSpec, true when an asset without that member is invalid.\n"
    "stem|Use at most once on an abnd:Asset bound by naming convention, giving the basename its members share.\n",
)


# Module notes, by ontology IRI.
SCOPE_NOTES["https://hexplain.io/ns/core"] = (
    "Import to link a physical description (bddo, dlv) to the RDF it emits: class and property mappings, "
    "conditional mappings, computed values, encoding pipelines, register bindings and the register lifecycle. It "
    "adds no byte-layout terms of its own."
)
SCOPE_NOTES["https://hexplain.io/ns/aspect/bundle"] = (
    "Import to describe an asset made of several files, or of several members of one container, and the reusable "
    "profiles that say which members such an asset has. It says nothing about the members' bytes: those are bddo "
    "descriptions named by abnd:describedBy."
)
SCOPE_NOTES["https://hexplain.io/ns/conf"] = (
    "Import to bind executable HEL assertions and parse attributions to the requirements they check, and to read "
    "or write the run reports of a Conformance Evaluator. Load conf/shapes.ttl to validate profiles and reports."
)
SCOPE_NOTES["https://hexplain.io/ns/req"] = (
    "Import to identify the requirements of a standards document that constraints cite and run reports account "
    "for. It describes what documents demand, not how a check is executed."
)
SCOPE_NOTES["https://hexplain.io/ns/conf/shapes"] = (
    "Load with the conf vocabulary to validate conformance profiles (constraints, parse attributions) and run "
    "reports (runs, outcomes, findings). A report validates on its own because it carries copies of the "
    "requirements, constraints and attributions it cites."
)
SCOPE_NOTES["https://hexplain.io/ns/req/shapes"] = (
    "Load with the req vocabulary to validate requirements: a non-blank identifier, standard and statement, one "
    "discrepancy type, and one requirement per normalised (standard, identifier) pair."
)
