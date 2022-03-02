from sys import argv
import shutil
import json
import os


ROOT = os.path.dirname(os.path.realpath(__file__))
with open(ROOT + '/index.html', 'r') as f:
    TEMPLATE = f.read()


def have_attr(node, attr):
    return any(i['name'] == attr for i in node['attributes'])


def inherited_attr(node, attr):
    attrs = [i for i in node['attributes'] if i['name'] == attr]
    if attrs and any(i['isInheritable'] for i in attrs):
        return 1
    if node['parent']:
        parent = inherited_attr(node['parent'], attr)
        if parent is not None:
            return 1 + parent
    return None


def is_included(node):
    if have_attr(node, 'private'):
        return False
    if have_attr(node, 'public') or have_attr(node, 'publicRoot'):
        return True

    private_depth = inherited_attr(node, 'private') or float('inf')
    public_depth = inherited_attr(node, 'public') or float('inf')
    root_depth = inherited_attr(node, 'publicRoot') or float('inf')
    return min(public_depth, root_depth) < private_depth


def node_name(node):
    result = node['title']
    if node.get('prefix'):
        result = node['prefix'] + ' – ' + result
    return result


def out_filename(dst, node, mkdir=False):
    if name := node.get('dataFileName'):
        if mkdir:
            os.makedirs(dst, exist_ok=True)
        dst += name
    else:
        dst += node.get('dirFileName')
        if mkdir:
            os.makedirs(dst, exist_ok=True)
        dst += '/index.html'
    return dst


def is_hidden(node):
    if node['type'] == 'image':
        return True
    if have_attr(node, 'unlisted'):
        return True
    return False


def find_sidebar_root(node):
    if have_attr(node, 'publicRoot'):
        return node
    if not node['parent']:
        return node
    return find_sidebar_root(node['parent'])


def build_sidebar(files, active, home):
    non_hidden = [f for f in files if (f['noteId'] == active['noteId'] or not is_hidden(f)) and is_included(f)]
    if not non_hidden:
        return

    yield '<ul>'
    for f in non_hidden:
        yield '<li>'

        if f['noteId'] == active['noteId']:
            yield '<span class="active">'
        else:
            yield '<span>'
        name = node_name(f)
        if path := f['dataPath']: 
            yield f'<a href="{home}{path}">{name}</a>'
        else:
            yield f'{name}'
        yield '</span>'

        yield from build_sidebar(f['children'], active, home)
        yield '</li>'
    yield '</ul>'


def sidebar_for(node, home):
    files = [find_sidebar_root(node)]
    return build_sidebar(files, node, home)


def collect_notes(files):
    result = {}
    for f in files:
        if f['isClone']:
            continue
        result[f['noteId']] = f
        result.update(collect_notes(f['children']))
    return result


def remove_clones(files, known=None):
    if known is None:
        known = collect_notes(files)

    newFiles = []
    for f in files:
        if f['isClone']:
            newFiles.append(known[f['noteId']])
        else:
            f['children'] = remove_clones(f['children'], known)
            newFiles.append(f)
    return newFiles


def ensure_children(files):
    for f in files:
        if (children := f.get('children')) is not None:
            children.sort(key=lambda x: x['notePosition'])
            ensure_children(children)
        else:
            f['children'] = []


def add_pathes(files, prefix='/'):
    for f in files:
        if filename := f.get('dataFileName'):
            f['dataPath'] = prefix + filename
        else:
            f['dataPath'] = None
        if f['children']:
            add_pathes(f['children'], prefix=prefix + f['dirFileName'] + '/')


def link_parent(files, parent=None):
    for f in files:
        f['parent'] = parent
        link_parent(f['children'], parent=f)


def copy_files():
    shutil.copytree(ROOT + '/../files', './out', copy_function=os.link, dirs_exist_ok=True)


def copy_styles():
    shutil.copytree(ROOT + '/static', './out/static')
    shutil.copyfile('tmp/style.css', './out/static/trilium.css')


def copy_netlify():
    shutil.copytree(f'./netlify', f'./out/netlify')
    shutil.copyfile(f'./netlify.toml', f'./out/netlify.toml')


def make_404():
    with open('./out/404.html', 'w') as f:
        f.write(TEMPLATE.format(
            home = '.',
            title = 'Not found',
            sidebar = '<ul><li><a href="/">Home</a></li></ul>',
            content = error_content(404)
        ))
    with open('./out/403.html', 'w') as f:
        f.write(TEMPLATE.format(
            home = '.',
            title = 'Access denied',
            sidebar = '<ul><li><a href="/">Home</a></li></ul>',
            content = error_content(403)
        ))


def extract_content(raw):
    START = '<body class="ck-content">'
    END = '</body>'
    return raw[raw.index(START) + len(START):raw.index(END)]


def error_content(text):
    vb = {
        404: {
            'x': 0,
            'y': -1.90625,
            'width': 24.171875,
            'height': 19.78125
        },
        403: {
            'x': 0,
            'y': -1.875,
            'width': 24.171875,
            'height': 19.734375
        },
    }[text]
    return f'''
        <svg viewBox="{vb['x']} {vb['y']} {vb['width']} {vb['height']}" style="max-height: 50vh; width: 100%">
            <text fill="hsl(0, 0%, 85%)" x="50%" y="50%" dominant-baseline="middle" text-anchor="middle">{text}</text>
        </svg>
    '''


def save_html(node, dst, reduced_nesting=None):
    if not is_included(node):
        content = error_content(403)
        return

    # name = '/'
    # for i in node_name(node):
    #     if i == ' ':
    #         name += '-'
    #     elif not i.isalnum():
    #         name += '_'
    #     else:
    #         name += i

    dst = out_filename(dst, node, mkdir=True)

    if node['type'] != 'text' or node['format'] != 'html':
        if existing := node.get('savedAt'):
            existing = os.path.relpath(existing, dst)[3:]
            os.symlink(existing, dst)
        else:
            node['savedAt'] = dst
            shutil.copy('./tmp' + node['dataPath'], dst)
        return
    elif node['dataPath']:
        with open('./tmp' + node['dataPath'], 'r') as f:
            content = f.read()
        content = extract_content(content)
    else:
        content = error_content(404)

    depth = dst.count('/')
    if reduced_nesting:
        depth -= 1
    if depth <= 2:
        home = '.'
    else:
        home = ('../' * (depth - 2)).strip('/')
    html = TEMPLATE.format(
        home = home,
        title = node_name(node),
        sidebar = ''.join(sidebar_for(node, home)),
        content = content
    )
    if reduced_nesting:
        html = html.replace('/' + reduced_nesting + '/', '/')
    with open(dst, 'w') as f:
        f.write(html)


def save_all(files, prefix='./out/', reduced_nesting=None):
    for f in files:
        save_html(f, prefix, reduced_nesting)
        if f['children']:
            save_all(f['children'], prefix=prefix + f['dirFileName'] + '/',
                    reduced_nesting=reduced_nesting)


def main():
    shutil.rmtree('out', ignore_errors=True)

    shutil.unpack_archive(argv[1], 'tmp')

    with open('tmp/!!!meta.json', 'r') as f:
        meta = json.load(f)
    files = meta['files']

    # Prepare whole tree
    files = [i for i in files if not i.get('noImport')]
    ensure_children(files)
    add_pathes(files)
    files = remove_clones(files)
    link_parent(files)

    reduced_nesting = None
    if len(files) == 1 and any(i['title'] == 'index' for i in files[0]['children']):
        reduced_nesting = files[0]['dirFileName']

    # Generate html
    os.makedirs('./out/')
    save_all(files, reduced_nesting=reduced_nesting)

    # Copy needed files
    copy_files()
    copy_styles()
    copy_netlify()
    make_404()
    if reduced_nesting:
        for i in os.listdir('./out/' + reduced_nesting):
            shutil.move(f'./out/{reduced_nesting}/{i}', f'./out/{i}')
        os.rmdir('./out/' + reduced_nesting)

    shutil.rmtree('tmp')


main()
