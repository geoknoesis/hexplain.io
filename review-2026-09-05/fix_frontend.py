from pathlib import Path
root=Path('D:/work/hexplain-saas/frontend')
def edit(rel,fn):
 p=root/rel;s=p.read_text(encoding='utf-8');p.write_text(fn(s),encoding='utf-8')
for rel,call,deps in [('app/runs/compare/page.tsx','api.compareRuns(from, to)','from, to'),('app/formats/[id]/diff/page.tsx','api.diff(id, from, to)','id, from, to')]:
 p=root/rel;s=p.read_text(encoding='utf-8');a=s.index('  const load = useCallback');b=s.index('\n  const label',a)
 s=s[:a]+'''  useEffect(() => {
    let active = true;
    setDiff(null); setError(null);
    if (!from || !to) return;
    '''+call+'''.then(value => { if (active) setDiff(value); })
      .catch(e => { if (active) setError(e instanceof Error ? e.message : String(e)); });
    return () => { active = false; };
  }, ['''+deps+''']);
'''+s[b:]
 s=s.replace('{diff && (','{!diff && !error && from && to && <p role="status">Loading comparison…</p>}\n      {diff && (')
 p.write_text(s,encoding='utf-8')
edit('app/formats/[id]/page.tsx',lambda s:s.replace("  const [busy, setBusy] = useState(false);","  const [busy, setBusy] = useState(false);\n  const [published, setPublished] = useState(false);")
 .replace('      setVersions(vs);','''      setVersions(vs);
      const current = [...vs].reverse().find(v => v.state === 'PUBLISHED');
      if (current && /^\\d+\\.\\d+\\.\\d+$/.test(current.semver)) {
        const parts = current.semver.split('.').map(Number); parts[2] += 1; setSemver(parts.join('.'));
      }''')
 .replace('  async function compile() {\n    setBusy(true);','  async function compile() {\n    setError(null); setPublished(false);\n    setBusy(true);')
 .replace('      setResult({\n        ok:', "      setPublished(v.state === 'PUBLISHED');\n      setResult({\n        ok:")
 .replace('onChange={(e) => setSource(e.target.value)}', 'disabled={busy}\n                onChange={(e) => { setSource(e.target.value); setResult(null); setPublished(false); setElapsed(null); }}')
 .replace('onChange={(e) => setRules(e.target.value)}','disabled={busy}\n                onChange={(e) => { setRules(e.target.value); setResult(null); setPublished(false); }}')
 .replace("result.ok ? 'PUBLISHED' : 'INVALID'", "result.ok ? (published ? 'PUBLISHED' : 'COMPILED') : 'INVALID'")
 .replace('value={detail.profileTurtle}','value={result?.profileTurtle ?? detail.profileTurtle}')
 .replace('<span>Compiled profile · RDF</span>','<span>{result?.profileTurtle ? \'Compiled candidate · RDF\' : \'Stored version · RDF\'}</span>'))
edit('lib/api.ts',lambda s:s.replace('  error: string | null;\n};','  error: string | null;\n  semanticRdf?: string | null;\n};'))
p=root/'app/files/[id]/page.tsx';s=p.read_text(encoding='utf-8')
s=s.replace('  const gotoRef = useRef<HTMLInputElement>(null);','''  const gotoRef = useRef<HTMLInputElement>(null);
  const hexRef = useRef<HTMLDivElement>(null);
  const [bytePage, setBytePage] = useState(0);
  const pageSize = 1024;
  const [gotoError, setGotoError] = useState('');''')
s=s.replace("        setVersionId(opts[0].id);", "        const requested = new URLSearchParams(window.location.search).get('profileVersionId');\n        setVersionId(opts.some(o => o.id === requested) ? requested : opts[0].id);")
a=s.index('  useEffect(() => {\n    if (!versionId)');b=s.index('\n  const fields',a)
s=s[:a]+'''  useEffect(() => {
    let active = true;
    setView(null); setError(null); setSelectedId(null); setHoverId(null); setCaret(0); setBytePage(0);
    if (!versionId) return;
    api.fileView(id, versionId).then(v => {
      if (!active) return;
      setView(v);
      const offset = Number(new URLSearchParams(window.location.search).get('offset') ?? 0);
      if (Number.isSafeInteger(offset) && offset >= 0 && offset < v.sizeBytes) { setCaret(offset); setBytePage(Math.floor(offset / pageSize)); }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : String(e)); });
    return () => { active = false; };
  }, [id, versionId]);
'''+s[b:]
a=s.index('  const owner = useMemo');b=s.index('\n  const byId',a)
s=s[:a]+'''  // Interval lookup avoids allocating one object reference per file byte.
  const ownerAt = useCallback((i: number) => {
    for (let n = fields.length - 1; n >= 0; n--) { const f = fields[n]; if (f.start != null && f.end != null && i >= f.start && i < f.end) return f; }
    return null;
  }, [fields]);
  const bytes = useMemo(() => {
    const text = view?.hex ?? '';
    return Uint8Array.from({ length: text.length / 2 }, (_, i) => parseInt(text.slice(i * 2, i * 2 + 2), 16));
  }, [view?.hex]);
  useEffect(() => {
    setBytePage(Math.floor(caret / pageSize));
  }, [caret]);
  useEffect(() => {
    hexRef.current?.querySelector('.caret')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [caret, bytePage]);
'''+s[b:]
s=s.replace('owner[i]', 'ownerAt(i)').replace('owner[i - 1]','ownerAt(i - 1)').replace('owner[i + 1]','ownerAt(i + 1)').replace('[owner],','[ownerAt],')
s=s.replace("      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;", "      if (target && (target.closest('[role=tree]') || target.closest('button') || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) return;")
a=s.index('  const bytes: number[] = []');b=s.index('\n  const rawOf',a)
s=s[:a]+'''  const rows: number[] = [];
  for (let r = bytePage * pageSize; r < Math.min(bytes.length, (bytePage + 1) * pageSize); r += 16) rows.push(r);
'''+s[b:]
s=s.replace('slice.map(hex2).join', 'Array.from(slice, hex2).join')
s=s.replace("? parseInt(t.slice(2), 16)", "? (/^[0-9a-f]+$/i.test(t.slice(2)) ? parseInt(t.slice(2), 16) : NaN)")
s=s.replace('                      setGoto(null);','                      setGoto(null); setGotoError(\'\');',1).replace("                    }\n                  }}\n                />", "                    } else setGotoError('Enter an offset within this file.');\n                  }}\n                />",1)
s=s.replace('<span className="hint">Enter to jump · Esc to cancel</span>', '<span className="hint">Enter to jump · Esc to cancel</span><span role="alert">{gotoError}</span>')
s=s.replace('<div className="hexwrap">','''<div className="row" aria-label="Byte pages">
              <button className="btn sm" disabled={bytePage === 0} onClick={() => selectByte((bytePage - 1) * pageSize)}>Previous bytes</button>
              <span role="status">Page {bytePage + 1} of {Math.max(1, Math.ceil(bytes.length / pageSize))}</span>
              <button className="btn sm" disabled={(bytePage + 1) * pageSize >= bytes.length} onClick={() => selectByte((bytePage + 1) * pageSize)}>Next bytes</button>
            </div>
            <div className="hexwrap" ref={hexRef}>''')
s=s.replace('<div className="tree">','<div className="tree" role="tree" aria-label="File structure">')
s=s.replace('<span>Semantics</span><span className="grow">{triples.length} triples</span>', '<span>Mapping previews</span><span className="grow">{triples.length} mapped fields</span>')
s=s.replace('Triples lifted from mapped fields. Each carries the byte range it came from, so\n                meaning is always traceable back to the stream.', 'Raw field mapping previews; computed values, conditional mappings, typed literals and units are authoritative only in the lifted RDF graph below.')
s=s.replace('produces no triples. Add a', 'has no direct literal mapping previews. Add a')
s=s.replace('                    className={`triple', '                    role="button"\n                    tabIndex={0}\n                    onKeyDown={e => { if (e.key === \'Enter\' || e.key === \' \') { e.preventDefault(); setSelectedId(f.id); if(f.start != null) setCaret(f.start); } }}\n                    className={`triple')
s=s.replace('      {view.error &&', '''      <details className="panel"><summary>Lifted RDF graph · authoritative semantics</summary>
        <textarea className="code" readOnly aria-label="Lifted RDF graph" value={view.semanticRdf ?? 'No graph available.'} />
      </details>
      {view.error &&''')
s=s.replace('role="button"\n        tabIndex={0}', 'role="treeitem"\n        aria-expanded={hasChildren ? open : undefined}\n        aria-selected={node.id === selectedId}\n        tabIndex={0}')
s=s.replace("onKeyDown={(e) => { if (e.key === 'Enter') onSelect(node); }}", """onKeyDown={(e) => {
          e.stopPropagation();
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(node); }
          if (e.key === 'ArrowRight' && hasChildren) { e.preventDefault(); setOpen(true); }
          if (e.key === 'ArrowLeft' && hasChildren) { e.preventDefault(); setOpen(false); }
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault(); const tree=e.currentTarget.closest('[role=tree]');
            const items=Array.from(tree?.querySelectorAll<HTMLElement>('[role=treeitem]') ?? []);
            const next=items[items.indexOf(e.currentTarget) + (e.key === 'ArrowDown' ? 1 : -1)]; next?.focus();
          }
        }}""")
s=s.replace('          className="tw"\n          onClick', '          className="tw"\n          aria-hidden="true"\n          onClick')
p.write_text(s,encoding='utf-8')
edit('app/runs/[id]/page.tsx',lambda s:s.replace("? `@ 0x${f.byteOffset.toString(16).toUpperCase().padStart(4, '0')}`", "? <Link href={`/files/${run.fileId}?profileVersionId=${encodeURIComponent(run.tuple.profileVersionId)}&offset=${f.byteOffset}`}>{`@ 0x${f.byteOffset.toString(16).toUpperCase().padStart(4, '0')}`}</Link>"))
edit('app/layout.tsx',lambda s:s.replace('<Link href="/runs">Runs</Link>','<Link href="/runs">Runs</Link>\n              <a href="/login">Sign in</a>'))
