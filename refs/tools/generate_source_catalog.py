#!/usr/bin/env python3
"""Generate/check/query a deterministic sharded source catalog for bounded agent discovery."""
from __future__ import annotations
import argparse, ast, hashlib, re, subprocess
from pathlib import Path
from typing import Any
try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required: python -m pip install pyyaml") from exc

VERSION, BUCKETS = 1, 32
INDEX = Path("refs/implementation/sourceCatalog")
SHARDS = Path("refs/implementation/.sourceCatalogShards")
SCHEMA = "refs/schemas/schemaRegistry.yaml"
LANG = {
    ".py":"python", ".pyi":"python", ".ts":"typescript", ".tsx":"typescript", ".js":"javascript", ".jsx":"javascript",
    ".mjs":"javascript", ".cjs":"javascript", ".cs":"csharp", ".java":"java", ".kt":"kotlin", ".kts":"kotlin",
    ".go":"go", ".rs":"rust", ".gd":"gdscript", ".c":"c", ".h":"c_cpp", ".cc":"c_cpp", ".cpp":"c_cpp",
    ".cxx":"c_cpp", ".hpp":"c_cpp", ".swift":"swift", ".rb":"ruby", ".php":"php", ".vue":"vue", ".svelte":"svelte",
}
EXCLUDE = {".git",".venv","venv","node_modules","vendor","dist","build","target","coverage","__pycache__"}
CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_.]*)\s*\(")
TOK = re.compile(r"[a-z0-9]+")


def root() -> Path: return Path(__file__).resolve().parents[2]
def run(repo: Path, *args: str, binary=False):
    try: p = subprocess.run(["git", *args], cwd=repo, capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired): return None
    if p.returncode: return None
    return p.stdout if binary else p.stdout.decode("utf-8", errors="replace")
def source(path: str) -> bool:
    p = path.replace("\\", "/")
    return not p.startswith(("refs/", ".github/")) and not any(x in EXCLUDE for x in Path(p).parts) and Path(p).suffix.lower() in LANG


def entries(repo: Path) -> list[tuple[str,str]]:
    raw = run(repo, "ls-files", "-s", "-z", binary=True)
    if raw is None: raise SystemExit("Source catalog requires a Git working tree.")
    files: dict[str,str] = {}
    for row in raw.split(b"\0"):
        if row and b"\t" in row:
            meta, name = row.split(b"\t",1); fields = meta.decode().split()
            if len(fields) >= 3 and fields[2] == "0": files[name.decode(errors="surrogateescape").replace("\\","/")] = fields[1]
    dirty_raw = run(repo, "diff", "--name-only", "-z", binary=True) or b""
    dirty = {x.decode(errors="surrogateescape").replace("\\","/") for x in dirty_raw.split(b"\0") if x}
    other = run(repo, "ls-files", "--others", "--exclude-standard", "-z", binary=True) or b""
    for x in other.split(b"\0"):
        if x: files[x.decode(errors="surrogateescape").replace("\\","/")] = ""
    out=[]
    for name, indexed in files.items():
        f=repo/name
        if not source(name) or not f.is_file(): continue
        digest = indexed if indexed and name not in dirty else str(run(repo,"hash-object","--",name) or "").strip()
        out.append((name, digest or hashlib.sha256(f.read_bytes()).hexdigest()))
    return sorted(out)


def split_params(value: str) -> list[str]:
    out, cur, depth = [], [], 0
    for c in value:
        if c in "([{<": depth += 1
        elif c in ")]}>" and depth: depth -= 1
        if c == "," and not depth:
            if "".join(cur).strip(): out.append(" ".join("".join(cur).split()))
            cur=[]
        else: cur.append(c)
    if "".join(cur).strip(): out.append(" ".join("".join(cur).split()))
    return out
def safe_params(value: str) -> list[str]:
    out=[]
    for item in split_params(value):
        item=re.sub(r"\s*=.*$", "", item).strip()
        item=re.sub(r"([:\s])['\"].*", r"\1<literal omitted>", item).strip()
        if item: out.append(item)
    return out
def calls(body: str, own: str) -> list[str]:
    skip={"if","for","while","switch","catch","return",own}
    return sorted(dict.fromkeys(m.group(1) for m in CALL.finditer(body) if m.group(1).rsplit(".",1)[-1] not in skip))[:24]
def line(text: str, at: int) -> int: return text.count("\n",0,at)+1
def brace_end(text: str, start: int) -> int:
    depth=0; quote=None; escaped=False
    for i in range(start,len(text)):
        c=text[i]
        if quote:
            if escaped: escaped=False
            elif c=="\\": escaped=True
            elif c==quote: quote=None
        elif c in {'"',"'","`"}: quote=c
        elif c=="{": depth+=1
        elif c=="}":
            depth-=1
            if depth==0:return i+1
    return len(text)
def sym(name: str, kind: str, text: str, start: int, end: int, params: str, output: str, parser: str) -> dict[str,Any]:
    inputs=safe_params(params); result=" ".join((output or "unspecified").split())
    signature=f"{name}({', '.join(inputs)})" + (f" -> {result}" if result!="unspecified" else "")
    return {"name":name,"kind":kind,"line_start":line(text,start),"line_end":line(text,max(start,end-1)),"signature":signature,
            "inputs":inputs,"output":result,"dependencies":calls(text[start:end],name.rsplit(".",1)[-1]),"parser":parser}


def python_symbols(text: str):
    try: tree=ast.parse(text)
    except SyntaxError as e: return [],[],f"SyntaxError line {e.lineno}: {e.msg}"
    parents={}; deps=[]
    for p in ast.walk(tree):
        for c in ast.iter_child_nodes(p): parents[c]=p
        if isinstance(p,ast.Import): deps += [a.name for a in p.names]
        elif isinstance(p,ast.ImportFrom): deps.append("."*p.level+(p.module or ""))
    offsets=[0]
    for row in text.splitlines(keepends=True): offsets.append(offsets[-1]+len(row))
    out=[]
    for n in ast.walk(tree):
        if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
        chain=[n.name]; cur=parents.get(n); method=False
        while cur:
            if isinstance(cur,ast.ClassDef): chain.append(cur.name); method=True
            elif isinstance(cur,(ast.FunctionDef,ast.AsyncFunctionDef)): chain.append(cur.name)
            cur=parents.get(cur)
        name=".".join(reversed(chain)); args=[ast.unparse(a) for a in n.args.posonlyargs+n.args.args]
        if n.args.vararg: args.append("*"+ast.unparse(n.args.vararg))
        args += [ast.unparse(a) for a in n.args.kwonlyargs]
        if n.args.kwarg: args.append("**"+ast.unparse(n.args.kwarg))
        output=ast.unparse(n.returns) if n.returns else "unspecified"; start=offsets[n.lineno-1]; end=offsets[min(n.end_lineno or n.lineno,len(offsets)-1)]
        item=sym(name,"method" if method else "function",text,start,end,", ".join(args),output,"python-ast")
        found=[]
        for c in ast.walk(n):
            if isinstance(c,ast.Call):
                try: found.append(ast.unparse(c.func))
                except Exception: pass
        item["dependencies"]=sorted(dict.fromkeys(x for x in found if x.rsplit(".",1)[-1]!=n.name))[:24]; out.append(item)
    return sorted(dict.fromkeys(x for x in deps if x)),sorted(out,key=lambda x:(x["line_start"],x["name"])),None


def imports(text: str, lang: str) -> list[str]:
    patterns={
        "js":[r"\bfrom\s+['\"]([^'\"]+)",r"\brequire\s*\(\s*['\"]([^'\"]+)"],
        "csharp":[r"(?m)^\s*using\s+(?:static\s+)?([A-Za-z_][\w.]*)\s*;"],
        "jvm":[r"(?m)^\s*import\s+([A-Za-z_][\w.*]*)"], "cpp":[r"(?m)^\s*#\s*include\s*[<\"]([^>\"]+)"],
        "rust":[r"(?m)^\s*use\s+([^;]+);"], "gd":[r"\b(?:preload|load)\s*\(\s*['\"]([^'\"]+)"],
        "ruby":[r"(?m)^\s*require(?:_relative)?\s+['\"]([^'\"]+)"], "php":[r"(?m)^\s*use\s+([^;]+);"],
    }
    family = "js" if lang in {"typescript","javascript","vue","svelte"} else "jvm" if lang in {"java","kotlin","swift"} else "cpp" if lang in {"c","c_cpp"} else "gd" if lang=="gdscript" else lang
    return sorted(dict.fromkeys(m.group(1).strip() for p in patterns.get(family,[]) for m in re.finditer(p,text)))[:32]


def regex_symbols(text: str, lang: str) -> list[dict[str,Any]]:
    specs=[]
    if lang in {"typescript","javascript","vue","svelte"}:
        specs=[(r"(?m)^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)\s*(?::\s*([^\n{]+))?\s*\{","function",1,2,3),
               (r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=\n]+)?=\s*(?:async\s*)?\(([^)]*)\)\s*(?::\s*([^=\n]+))?\s*=>\s*\{","function",1,2,3),
               (r"(?m)^\s*(?:(?:public|private|protected|static|async|override)\s+)*([A-Za-z_$][\w$]*)\s*\(([^)]*)\)\s*(?::\s*([^\n{]+))?\s*\{","method",1,2,3)]
    elif lang=="go": specs=[(r"(?m)^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(([^)]*)\)\s*([^\n{]*)\s*\{","function",1,2,3)]
    elif lang=="rust": specs=[(r"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)[^\n(]*\(([^)]*)\)\s*(?:->\s*([^\n{]+))?\s*\{","function",1,2,3)]
    elif lang=="gdscript": specs=[(r"(?m)^\s*(?:static\s+)?func\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*(?:->\s*([^:\n]+))?\s*:","function",1,2,3)]
    elif lang=="ruby": specs=[(r"(?m)^\s*def\s+([A-Za-z_]\w*[!?=]?)\s*(?:\(([^)]*)\))?","function",1,2,0)]
    else: specs=[(r"(?m)^\s*(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|final|suspend|inline|extern|constexpr)\s+)*([A-Za-z_][\w<>,.\[\]?*&: ]*)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)[^\n{]*\{","method",2,3,1)]
    out=[]; seen=set()
    for pattern,kind,ni,pi,oi in specs:
        matches=list(re.finditer(pattern,text))
        for i,m in enumerate(matches):
            name=m.group(ni)
            if name in {"if","for","while","switch","catch"} or (m.start(),name) in seen: continue
            seen.add((m.start(),name)); opening=text.find("{",m.start(),m.end()); end=brace_end(text,opening) if opening>=0 else (matches[i+1].start() if i+1<len(matches) else len(text))
            out.append(sym(name,kind,text,m.start(),end,m.group(pi) or "",m.group(oi).strip() if oi and m.group(oi) else "unspecified",f"{lang}-pattern"))
    return sorted(out,key=lambda x:(x["line_start"],x["name"]))


def parse(repo: Path, path: str, digest: str) -> dict[str,Any]:
    text=(repo/path).read_text(encoding="utf-8",errors="replace"); lang=LANG[Path(path).suffix.lower()]; error=None
    if lang=="python": deps,symbols,error=python_symbols(text)
    else: deps,symbols=imports(text,lang),regex_symbols(text,lang)
    item={"path":path,"analysis_version":VERSION,"language":lang,"content_hash":digest,"dependencies":deps,"provides":[s["name"] for s in symbols],"symbols":symbols}
    if error:item["parse_error"]=error
    return item


def shard_dir(repo: Path)->Path:return repo/SHARDS
def old_records(repo: Path)->dict[str,dict[str,Any]]:
    out={}
    for path in sorted(shard_dir(repo).glob("shard-*.yaml")) if shard_dir(repo).is_dir() else []:
        try:data=yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError:continue
        for item in (data.get("source_catalog") or {}).get("files") or []:
            if isinstance(item,dict) and item.get("path"):out[item["path"]]=item
    return out
def dump(data: dict[str,Any])->str:return yaml.safe_dump(data,sort_keys=False,allow_unicode=False,width=120)
def resolve(records: list[dict[str,Any]])->None:
    names={}
    for f in records:
        for s in f.get("symbols") or []: names.setdefault(str(s.get("name") or "").rsplit(".",1)[-1],[]).append({"path":f["path"],"symbol":s["name"]})
    for f in records:
        for s in f.get("symbols") or []:
            targets=[]
            for dep in s.get("dependencies") or []:
                matches=names.get(str(dep).rsplit(".",1)[-1],[])
                if len(matches)<=4: targets += [x for x in matches if x!={"path":f["path"],"symbol":s["name"]}]
            s["dependency_targets"]=list({(x["path"],x["symbol"]):x for x in targets}.values())[:24]


def build(repo: Path):
    old=old_records(repo); records=[]
    for path,digest in entries(repo):
        cached=old.get(path); records.append(cached if cached and cached.get("analysis_version")==VERSION and cached.get("content_hash")==digest else parse(repo,path,digest))
    records.sort(key=lambda x:x["path"]); resolve(records); buckets={}
    for item in records:buckets.setdefault(hashlib.sha256(item["path"].encode()).digest()[0]%BUCKETS,[]).append(item)
    shards={}; summary=[]
    for bucket,files in sorted(buckets.items()):
        name=f"shard-{bucket:02x}.yaml"; shards[name]=dump({"version":1,"schema":SCHEMA,"source_catalog":{"format_version":VERSION,"bucket":f"{bucket:02x}","files":files}})
        summary.append({"path":f"{SHARDS.as_posix()}/{name}","files":len(files),"symbols":sum(len(f.get("symbols") or []) for f in files)})
    languages={}; parsers={}
    for f in records:
        languages[f["language"]]=languages.get(f["language"],0)+1
        for s in f.get("symbols") or []:parsers[s["parser"]]=parsers.get(s["parser"],0)+1
    index={"version":1,"schema":SCHEMA,"source_catalog":{"format_version":VERSION,"generated_by":"refs/tools/generate_source_catalog.py","derived":True,"tracked_source_files":len(records),"symbols":sum(len(f.get("symbols") or []) for f in records),"languages":dict(sorted(languages.items())),"parsers":dict(sorted(parsers.items())),"shards":summary,"query_command":'python refs/tools/generate_source_catalog.py --query "<task or symbol>"',"notes":["Generated from source; never hand-edit this catalog or its shards.","Use catalog query results and symbol line ranges before opening whole source files.","Inputs, outputs, imports, and call dependencies are static-analysis hints; runtime/dynamic behavior still requires source or tests when relevant."]}}
    return dump(index),shards,records


def refresh(repo: Path):
    index,shards,records=build(repo); idir=repo/INDEX; sdir=repo/SHARDS; idir.mkdir(parents=True,exist_ok=True); sdir.mkdir(parents=True,exist_ok=True); changed=[]
    for p in sdir.glob("shard-*.yaml"):
        if p.name not in shards:p.unlink();changed.append(p.relative_to(repo).as_posix())
    ip=idir/"index.yaml"
    if not ip.is_file() or ip.read_text()!=index:ip.write_text(index);changed.append(ip.relative_to(repo).as_posix())
    for name,content in shards.items():
        p=sdir/name
        if not p.is_file() or p.read_text()!=content:p.write_text(content);changed.append(p.relative_to(repo).as_posix())
    return records,changed
refresh_catalog=refresh

def check_catalog(repo: Path):
    index,shards,_=build(repo); idir=repo/INDEX; sdir=repo/SHARDS; problems=[]; ip=idir/"index.yaml"
    if not ip.is_file():problems.append(f"missing {ip.relative_to(repo).as_posix()}")
    elif ip.read_text()!=index:problems.append(f"stale {ip.relative_to(repo).as_posix()}")
    for name,content in shards.items():
        p=sdir/name
        if not p.is_file():problems.append(f"missing {p.relative_to(repo).as_posix()}")
        elif p.read_text()!=content:problems.append(f"stale {p.relative_to(repo).as_posix()}")
    actual={p.name for p in sdir.glob("shard-*.yaml")} if sdir.is_dir() else set()
    problems += [f"unexpected {SHARDS.as_posix()}/{name}" for name in sorted(actual-set(shards))]
    return not problems,problems
def records(repo: Path)->list[dict[str,Any]]:return sorted(old_records(repo).values(),key=lambda x:x["path"])
def tokens(value: str)->set[str]:return {t for t in TOK.findall(re.sub(r"([a-z0-9])([A-Z])",r"\1 \2",value).casefold()) if len(t)>1}
def query_records(items: list[dict[str,Any]], query: str, limit=12):
    wanted=tokens(query); ranked=[]
    for f in items:
        path=f.get("path",""); base=4*len(tokens(path)&wanted)+2*len(tokens(" ".join(f.get("dependencies") or []))&wanted)
        for s in f.get("symbols") or []:
            score=base+8*len(tokens(s.get("name",""))&wanted)+3*len(tokens(s.get("signature",""))&wanted)+2*len(tokens(" ".join(s.get("dependencies") or []))&wanted)
            if score:ranked.append((score,{"path":path,"language":f.get("language"),"symbol":s,"file_dependencies":f.get("dependencies") or []}))
        if base and not f.get("symbols"):ranked.append((base,{"path":path,"language":f.get("language"),"symbol":None,"file_dependencies":f.get("dependencies") or []}))
    ranked.sort(key=lambda x:(x[0],str((x[1].get("symbol") or {}).get("name") or ""),x[1]["path"]),reverse=True);return [x for _,x in ranked[:limit]]
def query_catalog(repo: Path, query: str, limit=12):return query_records(records(repo),query,limit)


def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--check",action="store_true");p.add_argument("--query");p.add_argument("--max-results",type=int,default=12);a=p.parse_args();repo=root()
    if a.check:
        if a.query:raise SystemExit("--check and --query cannot be combined")
        ok,problems=check_catalog(repo)
        if not ok:raise SystemExit("source catalog check failed:\n- "+"\n- ".join(problems))
        items=records(repo);print(f"source catalog check ok: {len(items)} files, {sum(len(x.get('symbols') or []) for x in items)} symbols");return 0
    items,changed=refresh(repo)
    if a.query:
        found=query_records(items,a.query,a.max_results);print("Source catalog matches:" if found else "No source catalog matches.")
        for item in found:
            s=item.get("symbol")
            if not s:print(f"- {item['path']} (file match)");continue
            deps=s.get("dependencies") or []; suffix=f"; calls: {', '.join(deps[:6])}" if deps else ""
            print(f"- {item['path']}:{s['line_start']}-{s['line_end']} | {s['signature']} | returns: {s.get('output') or 'unspecified'}{suffix}")
    else:print(f"source catalog {'updated' if changed else 'already current'}: {len(items)} files, {sum(len(x.get('symbols') or []) for x in items)} symbols")
    return 0
if __name__=="__main__":raise SystemExit(main())
