"""Small explicit catalog; technical error details remain bilingual."""
LANGUAGE = 'zh'

STRINGS = {
    'playback_controls':('多媒体控件','Playback controls'),
    'replace_text':('替换文字批注','Replace text'), 'squiggly':('波浪下划线','Squiggly underline'), 'caret':('插入文字','Insert text'), 'add_video':('插入视频','Insert video'),
    'minimap':('速览窗','Quick overview'),
    'text_ops':('文字操作','Text tools'), 'vector_edit':('图形编辑','Shape editing'),
    'colors':('颜色替换','Replace colors'), 'organize':('组织页面','Organize pages'),
    'print':('打印…','Print…'), 'file_info':('文件信息','Document information'),
    'sidebar':('导航栏','Navigation'), 'toolbar':('工具栏','Toolbar'),

    'file': ('文件', 'File'), 'open': ('打开文件…', 'Open document…'),
    'save': ('保存', 'Save'), 'save_as': ('另存为…', 'Save as…'),
    'close': ('关闭标签页', 'Close tab'), 'recent': ('最近文件', 'Recent files'),
    'edit': ('编辑', 'Edit'), 'undo': ('撤销', 'Undo'), 'redo': ('重做', 'Redo'),
    'view': ('视图', 'View'), 'help': ('帮助', 'Help'), 'about': ('关于 AsterPDF', 'About AsterPDF'),
    'update': ('检查 GitHub 更新…', 'Check GitHub updates…'),
    'export_settings': ('导出设置…','Export settings…'), 'language': ('语言','Language'), 'dark': ('深色界面', 'Dark interface'),
    'night': ('夜间页面显示', 'Night page colors'), 'fullscreen': ('全屏', 'Full screen'),
    'presentation': ('演示模式', 'Presentation'), 'continuous': ('连续滚动', 'Continuous'),
    'page_fit': ('适合页面', 'Fit page'), 'width_fit': ('适合宽度', 'Fit width'),
    'read': ('阅读', 'Read'), 'hand': ('手形平移', 'Hand / pan'), 'select': ('文字与图片选择', 'Select text / images'), 'region': ('框选区域', 'Select region'),
    'annotate': ('批注', 'Annotate'), 'objects': ('对象编辑', 'Edit objects'),
    'pages': ('页面操作', 'Page operations'), 'extract': ('提取 / 导出', 'Extract / export'),
    'media': ('动画 / 媒体', 'Animation / media'), 'outline': ('目录', 'Outline'),
    'bookmarks': ('书签', 'Bookmarks'), 'bookmark': ('添加 / 移除阅读书签', 'Toggle reading bookmark'),
    'search': ('搜索', 'Search'), 'search_hint': ('搜索文档，按 Enter', 'Search document, press Enter'),
    'thumbnails': ('缩略图', 'Thumbnails'), 'rotate': ('旋转 90°', 'Rotate 90°'),
    'delete_pages': ('删除页面…', 'Delete pages…'), 'blank': ('插入空白页', 'Insert blank page'),
    'merge': ('合并 PDF…', 'Merge PDFs…'), 'split': ('拆分 PDF…', 'Split PDF…'),
    'extract_pages': ('提取选定页面…', 'Extract pages…'), 'crop': ('裁剪页面', 'Crop page'),
    'export_pages': ('导出页面图片…', 'Export page images…'),
    'export_region': ('导出区域图片…', 'Export region image…'),
    'copy_region': ('复制高清区域图片…', 'Copy high resolution region…'),
    'vector_pdf': ('导出局部矢量 PDF…', 'Export vector region PDF…'),
    'images': ('提取内嵌原始图片…', 'Extract embedded images…'),
    'highlight': ('高亮', 'Highlight'), 'underline': ('下划线', 'Underline'),
    'strikeout': ('删除线', 'Strikeout'), 'note': ('便笺', 'Note'), 'freetext': ('文本批注', 'Text annotation'),
    'ink': ('自由画笔', 'Freehand'), 'line': ('线条', 'Line'), 'arrow': ('箭头', 'Arrow'),
    'rectangle': ('矩形', 'Rectangle'), 'ellipse': ('椭圆', 'Ellipse'),
    'select_annot': ('选择批注', 'Select annotation'), 'color': ('颜色', 'Color'),
    'width': ('线宽', 'Line width'), 'opacity': ('不透明度', 'Opacity'),
    'add_text': ('添加文字', 'Add text'), 'add_image': ('插入图片', 'Insert image'),
    'scan_objects': ('识别当前页对象', 'Inspect page objects'),
    'modify': ('修改所选对象…', 'Edit selected object…'), 'transform': ('移动 / 缩放…', 'Move / scale…'),
    'delete_object': ('删除所选对象', 'Delete selected objects'), 'replace_image': ('替换图片…', 'Replace image…'),
    'extract_image': ('提取所选图片…', 'Extract selected image…'),
    'select_pages': ('页码 / 范围（例如 1,3-5）', 'Pages / ranges (e.g. 1,3-5)'),
    'cancel': ('取消', 'Cancel'), 'apply': ('应用', 'Apply'), 'done': ('完成', 'Done'),
    'working': ('正在处理…', 'Working…'), 'ready': ('就绪 · 本地处理', 'Ready · Local processing'),
    'empty': ('打开一份文档，开始阅读与探索', 'Open a document. Make room for discovery.'),
    'drop': ('拖放 PDF 文件到这里，或按 Ctrl+O', 'Drop PDF files here, or press Ctrl+O'),
    'need_region': ('请先使用“框选区域”拖出一个矩形。', 'Draw a rectangle with Select region first.'),
    'need_object': ('请在页面上选择对象。', 'Select an object on the page.'),
    'unsaved': ('文档有未保存修改。是否保存？', 'This document has unsaved changes. Save them?'),
    'no_media': ('未识别到支持的动画或内嵌媒体。', 'No supported animation or embedded media found.'),
    'play': ('播放 / 暂停', 'Play / pause'), 'replay': ('重播', 'Replay'), 'loop': ('循环', 'Loop'),
    'first': ('首帧', 'First'), 'last': ('末帧', 'Last'), 'previous': ('上一帧', 'Previous'),
    'next': ('下一帧', 'Next'), 'details': ('功能与兼容性说明', 'Features and compatibility'),
}


def tr(key):
    pair = STRINGS.get(key, (key, key))
    return pair[0 if LANGUAGE == 'zh' else 1]


PAIRS={}

def L(zh,en):
    if isinstance(zh,str) and isinstance(en,str) and len(PAIRS)<8192:
        PAIRS[zh]=(zh,en);PAIRS[en]=(zh,en)
    return zh if LANGUAGE=='zh' else en

def translated(value):
    for pair in STRINGS.values():
        if value in pair:return pair[0 if LANGUAGE=='zh' else 1]
    pair=PAIRS.get(value)
    return pair[0 if LANGUAGE=='zh' else 1] if pair else value
