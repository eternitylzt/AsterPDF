"""Consistent, nonmodal page-operation panes."""
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QLabel,QPushButton,QFileDialog,QDialogButtonBox,QBoxLayout
from .i18n import L,tr
from .core import pages_from_text,merge_files
from .cropping import crop_document


class PageToolsMixin:
    def page_tools(self,operation):
        if self.busy:return
        selected=self.selected_pages();organizing=self.organizer.isVisible()
        active=self.organizer.currentItem();current_page=active.data(Qt.UserRole) if organizing and active else self.canvas.page
        key={'delete':'delete_pages','rotate':'rotate','blank':'blank','extract':'extract_pages'}.get(operation,operation)
        pane=self.property_pane(tr(key));self.page_properties=pane;self.page_tool=operation
        self.set_mode('crop' if operation=='crop' else 'select')
        if operation!='crop' and self.active_panel=='pages':self.document_views.setCurrentWidget(self.organizer)
        scope=pane.choice('scope',L('应用范围','Apply to'),[(L('当前页','Current page'),'current'),(L('所有页面','All pages'),'all'),(L('指定范围','Page range'),'range'),(L('已选页面','Selected pages'),'selected')])
        pane.base_path=self.document.path;pane.selected_pages=selected;pane.current_page=current_page;pane.live=operation in ('rotate','flip_h','flip_v')
        pages=pane.text('pages',L('页码','Pages'),','.join(str(i+1) for i in selected))
        scope.currentIndexChanged.connect(lambda:pages.setEnabled(scope.currentData()=='range'))
        if len(selected)>1:scope.setCurrentIndex(3)
        pages.setEnabled(False)
        if operation=='rotate':pane.choice('angle',L('旋转角度','Rotation'),[(L('顺时针 90°','90° clockwise'),90),(L('逆时针 90°','90° counterclockwise'),-90),('180°',180)])
        if operation=='rotate':pane.inputs['angle'].setCurrentIndex(max(0,pane.inputs['angle'].findData(self.window.settings.value('page/angle',90,type=int))))
        if operation=='blank':
            pane.choice('position',L('插入位置','Insert'),[(L('所选页之后','After selected pages'),'after'),(L('所选页之前','Before selected pages'),'before')])
            pane.note(L('在范围内每一页的前/后插入同尺寸空白页。','Insert a matching blank page before/after each page in the scope.'))
        if operation=='extract':pane.check('separate',L('每页一个 PDF','One PDF per page'),self.window.settings.value('page/separate',False,type=bool))
        if operation=='crop':
            pane.check('keep',L('保留框外内容','Keep outside content'),self.window.settings.value('crop/keep',False,type=bool))
            for name,label in [('x',L('左边距（点）','Left (pt)')),('y',L('上边距（点）','Top (pt)')),('width',L('宽度（点）','Width (pt)')),('height',L('高度（点）','Height (pt)'))]:
                field=pane.number(name,label,0,0,200000,1);field.setEnabled(False);field.valueChanged.connect(self.crop_fields_changed)
            pane.note(L('拖框后可拖动边框与八个调节点。多页按相同比例裁剪。默认真实删除框外文字、图形及图片像素；跨边界的文字/矢量对象会整项移除。保留模式只改变可见框。',
                'Adjust the rectangle using its border/eight handles. Other page sizes use proportional margins. Default removes outside text, paths and image pixels; crossing text/path objects are removed whole. Keep mode changes only the visible box.'))
            pane.note(L('删除式裁剪暂不支持含表单/动画/媒体的目标页。仅处理目标页，不清理其它页、附件或撤销/恢复历史。','Destructive crop excludes pages with forms/animation/media. Other pages, attachments and undo/recovery history are not scrubbed.'))
        pane.feedback=QLabel();pane.feedback.setWordWrap(True);pane.form.addRow(pane.feedback)
        if operation in ('delete','blank','extract'):
            warnings=self.document.preflight(True)
            if warnings:pane.note('\n'.join(warnings))
        pane.apply_button=QPushButton(L('旋转','Rotate') if operation=='rotate' else L('翻转','Flip') if pane.live else tr('apply'));pane.apply_button.clicked.connect(self.apply_page_tools);pane.form.addRow(pane.apply_button)
        cancel=QPushButton(tr('cancel'));cancel.clicked.connect(self.cancel_page_tools);pane.form.addRow(cancel)
        if operation=='crop':self.crop_selection_changed()
        if pane.live:
            pane.note(L('点击操作即生效。退出此栏保留；取消撤回本栏本次旋转/翻转。','Each action takes effect immediately. Leaving keeps changes; Cancel reverses this session.'))
            if operation=='rotate':pane.inputs['angle'].activated.connect(lambda _:self.apply_page_tools())

    def cancel_page_tools(self):
        if self.busy:
            QTimer.singleShot(50,self.cancel_page_tools);return
        operations=getattr(self,'page_live_operations',[])[:];self.page_live_operations=[]
        if operations and not self.busy:
            def inverse(job):
                from .core import apply_page_transform
                base=getattr(self.page_properties,'base_path',None)
                if base in self.document.history:
                    self.document.release_rendering();self.document.index=self.document.history.index(base);self.document.revision+=1;self.document._metadata();return
                self.document.edit('cancel page transforms',lambda pdf:[apply_page_transform(pdf,op,indices,-angle if op=='rotate' else angle) for op,indices,angle in reversed(operations)])
            self.run(tr('pages'),inverse,editing=True)
        self.canvas.region=None;self.canvas.crop_drag=None;self.canvas.update();self.page_tool=None;self.close_properties()

    def crop_selection_changed(self):
        pane=getattr(self,'page_properties',None)
        if not pane or getattr(self,'page_tool',None)!='crop':return
        region=self.canvas.region
        pane.apply_button.setEnabled(bool(region))
        if not region:
            pane.feedback.setText(L('请在页面上拖出裁剪框。','Draw a crop rectangle on the page.'));return
        _,(x,y,x1,y1)=region
        for name,value in [('x',x),('y',y),('width',x1-x),('height',y1-y)]:
            field=pane.inputs[name];field.setEnabled(True);field.blockSignals(True);field.setValue(value);field.blockSignals(False)
        pane.feedback.setText(L('调整完成后点击“应用”。','Adjust the rectangle, then Apply.'))

    def crop_fields_changed(self):
        if not self.canvas.region:return
        v=self.page_properties.values();page=self.canvas.region[0];w,h=self.canvas.sizes[page]
        x=max(0,min(v['x'],w-1));y=max(0,min(v['y'],h-1))
        self.canvas.region=(page,(x,y,min(w,x+max(1,v['width'])),min(h,y+max(1,v['height']))))
        self.canvas.update()

    def apply_page_tools(self):
        pane=self.page_properties;v=pane.values();operation=self.page_tool
        if self.busy:return
        try:
            indices=list(range(self.info['count'])) if v['scope']=='all' else pages_from_text(v['pages'],self.info['count']) if v['scope']=='range' else self.selected_pages() if v['scope']=='selected' else [self.canvas.region[0] if operation=='crop' and self.canvas.region else (self.organizer.currentItem().data(Qt.UserRole) if self.organizer.isVisible() and self.organizer.currentItem() else pane.current_page)]
            if not indices or any(i>=self.info['count'] for i in indices):raise ValueError(L('请重新选择有效页码。','Select valid pages again.'))
            if operation=='delete' and len(indices)>=self.info['count']:raise ValueError(L('至少保留一页。','Keep at least one page.'))
            if operation=='crop' and not self.canvas.region:raise ValueError(tr('need_region'))
        except ValueError as error:pane.feedback.setText(str(error));return
        def failure(message):
            if getattr(self,'page_properties',None) is pane:pane.feedback.setText(str(message));pane.apply_button.setEnabled(True)
        def done(_):
            if pane.live and getattr(self,'page_properties',None) is pane:self.page_live_operations.append((operation,indices[:],v.get('angle',90)))
            if getattr(self,'page_properties',None) is not pane:return
            pane.apply_button.setEnabled(True);pane.feedback.setText(L('已生效。取消可撤回本栏操作。','Updated. Cancel reverses this session.') if pane.live else L('已应用，可撤销。','Applied. Undo is available.'))
            if operation=='crop':self.canvas.region=None;self.canvas.update();pane.apply_button.setEnabled(False)
            if operation in ('rotate','flip_h','flip_v'):
                for listing in (self.thumbnails,self.organizer):
                    listing.setCurrentRow(indices[0]);listing.clearSelection()
                    for n in range(listing.count()):listing.item(n).setSelected(n in indices)
            pane.selected_pages=[i for i in indices if i<self.info['count']]
        if operation=='extract':
            self.extract_with_options(indices,v['separate'],pane);return
        if operation=='crop':
            page,rect=self.canvas.region
            work=lambda j:crop_document(self.document,indices,page,rect,v['keep'])
        elif operation=='blank':
            work=lambda j:self.document.page_operation('blanks',indices,before=v['position']=='before')
        else:work=lambda j:self.document.page_operation(operation,indices,angle=v.get('angle',90))
        pane.apply_button.setEnabled(False);pane.feedback.setText(tr('working'))
        self.run(tr('pages'),work,done,editing=True,failure=failure)

    def extract_with_options(self,indices,separate,pane):
        if separate:
            directory=QFileDialog.getExistingDirectory(self,tr('extract_pages'))
            if not directory:return
            targets=[Path(directory)/f'{Path(self.document.original).stem}_p{i+1:04d}.pdf' for i in indices]
            if any(p.exists() for p in targets):pane.feedback.setText(L('文件已存在，请选择其它目录。','Files already exist; choose another folder.'));return
            def work(job):
                for n,(page,path) in enumerate(zip(indices,targets)):
                    if job.cancelled:break
                    self.document.extract_pages([page],path);job.signals.progress.emit(n+1,len(indices))
        else:
            filename,_=QFileDialog.getSaveFileName(self,tr('extract_pages'),'extracted.pdf','PDF (*.pdf)')
            if not filename:return
            if Path(filename).resolve()==Path(self.document.original).resolve():pane.feedback.setText(L('请使用新文件名。','Choose a new filename.'));return
            work=lambda job:self.document.extract_pages(indices,filename)
        self.run(tr('extract_pages'),work,lambda _:pane.feedback.setText(L('提取完成。','Export complete.')),failure=lambda e:pane.feedback.setText(str(e)),cancellable=separate)

    def merge_pane(self):
        from .dialogs import MergeDialog
        pane=self.property_pane(tr('merge'));self.page_properties=pane;self.page_tool='merge';self.set_mode('select')
        dialog=MergeDialog(self);dialog.setWindowFlags(Qt.Widget);dialog.setMinimumWidth(0);dialog.setMaximumWidth(265)
        dialog.list.setMinimumHeight(160);dialog.list.setMaximumHeight(260);dialog.setMaximumHeight(560)
        row=dialog.layout().itemAt(2).layout();row.setDirection(QBoxLayout.TopToBottom)
        dialog.layout().setContentsMargins(0,0,0,0)
        pane.form.addRow(dialog);dialog.show()
        dialog.buttons.accepted.disconnect();dialog.buttons.rejected.disconnect()
        dialog.buttons.rejected.connect(self.cancel_page_tools)
        def apply():
            files=dialog.files()
            if not files:return
            filename,_=QFileDialog.getSaveFileName(self,tr('merge'),'merged.pdf','PDF (*.pdf)')
            if not filename:return
            protected={Path(p).resolve() for p in files}|{Path(t.document.original).resolve() for t in self.window.document_tabs()}
            if Path(filename).resolve() in protected:dialog.note.setText(L('请使用新文件名。','Choose a new filename.'));return
            self.run(tr('merge'),lambda j:merge_files(files,filename),lambda _:self.window.open_file(filename),failure=lambda e:dialog.note.setText(str(e)))
        dialog.buttons.accepted.connect(apply)
        dialog.add_files([str(self.document.path)],{str(self.document.path):Path(self.document.original).name})
        dialog.note.setText(L('合并队列全部页面为新 PDF；文档级目录、脚本和表单树不会导入。可添加文件或已打开文档、拖动排序和移除。',
            'Merge the queue into a new PDF. Document outlines, scripts and form trees are not imported. Add files/open documents, reorder or remove.'))
