import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QLineEdit, QPushButton, QLabel, QListWidget,
                             QFileDialog, QSplitter, QProgressBar, QMessageBox, QTabWidget,
                             QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
                             QComboBox, QMenu, QAction)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor
from citation_identifier import CitationIdentifier
from rag_builder import RAGBuilder
from citation_validator import CitationValidator
from config_manager import ConfigManager


class WorkerThread(QThread):
    """工作线程，用于执行耗时的操作"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class RAGFrontend(QMainWindow):
    def __init__(self):
        super().__init__()
        # 初始化配置管理器
        self.config_manager = ConfigManager()

        # 从配置中加载API密钥和代理设置
        api_key = self.config_manager.get("api_key")
        use_proxy = self.config_manager.get("use_proxy", False)
        proxy_url = self.config_manager.get("proxy_url", "")
        last_index_path = self.config_manager.get("last_index_path", "")

        self.api_key = api_key
        self.citation_identifier = CitationIdentifier()

        # 初始化RAG构建器
        if api_key:
            self.rag_builder = RAGBuilder(api_key, use_proxy=use_proxy, proxy_url=proxy_url)
            self.citation_validator = CitationValidator(self.rag_builder)
        else:
            self.rag_builder = None
            self.citation_validator = None

        self.current_index_path = last_index_path

        self.init_ui()

        # 如果之前有加载索引，尝试自动加载
        if last_index_path and os.path.exists(f"{last_index_path}.index") and os.path.exists(f"{last_index_path}.json"):
            QTimer.singleShot(1000, self.auto_load_index)  # 延迟1秒加载，确保UI已初始化

    def auto_load_index(self):
        """自动加载索引"""
        try:
            last_index_path = self.config_manager.get("last_index_path", "")
            if last_index_path and os.path.exists(f"{last_index_path}.index") and os.path.exists(
                    f"{last_index_path}.json"):
                success = self.load_index(last_index_path, show_message=False)
                if success:
                    self.statusBar().showMessage(f"已自动加载索引: {os.path.basename(last_index_path)}")
        except Exception as e:
            print(f"自动加载索引失败: {str(e)}")

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("可信智撰")
        self.setGeometry(100, 100, 1200, 800)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建选项卡
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # 创建API设置选项卡
        self.api_tab = QWidget()
        self.setup_api_tab()
        self.tabs.addTab(self.api_tab, "API设置")

        # 创建RAG构建选项卡
        self.rag_tab = QWidget()
        self.setup_rag_tab()
        self.tabs.addTab(self.rag_tab, "RAG构建")

        # 创建引用验证选项卡
        self.verify_tab = QWidget()
        self.setup_verify_tab()
        self.tabs.addTab(self.verify_tab, "引用验证")

        # 初始化状态栏
        self.statusBar().showMessage("就绪")

    def setup_api_tab(self):
        """设置API选项卡"""
        layout = QVBoxLayout(self.api_tab)

        # API密钥输入
        api_group = QGroupBox("API设置")
        api_layout = QVBoxLayout(api_group)

        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(QLabel("API密钥:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("输入硅基流动API密钥")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText(self.config_manager.get("api_key", ""))
        api_key_layout.addWidget(self.api_key_input)

        self.save_api_btn = QPushButton("保存")
        self.save_api_btn.clicked.connect(self.save_api_key)
        api_key_layout.addWidget(self.save_api_btn)

        api_layout.addLayout(api_key_layout)

        # 代理设置
        proxy_layout = QHBoxLayout()
        proxy_layout.addWidget(QLabel("使用代理:"))
        self.use_proxy_checkbox = QCheckBox()
        self.use_proxy_checkbox.setChecked(self.config_manager.get("use_proxy", False))
        self.use_proxy_checkbox.stateChanged.connect(self.toggle_proxy_settings)
        proxy_layout.addWidget(self.use_proxy_checkbox)

        proxy_layout.addWidget(QLabel("代理地址:"))
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://proxy.example.com:8080")
        self.proxy_input.setText(self.config_manager.get("proxy_url", ""))
        self.proxy_input.setEnabled(self.config_manager.get("use_proxy", False))
        proxy_layout.addWidget(self.proxy_input)

        api_layout.addLayout(proxy_layout)
        layout.addWidget(api_group)

        # 状态信息
        status_group = QGroupBox("系统状态")
        status_layout = QVBoxLayout(status_group)

        self.api_status_label = QLabel("API密钥: " + ("已设置" if self.api_key else "未设置"))
        status_layout.addWidget(self.api_status_label)

        # 从配置中加载索引状态
        index_status = self.config_manager.get("index_status", {})
        status_text = f"RAG索引: {index_status.get('status', '未初始化')}"
        if index_status.get('status') == '已初始化':
            status_text += f" ({index_status.get('document_count', 0)} 个文档片段)"

        self.rag_status_label = QLabel(status_text)
        status_layout.addWidget(self.rag_status_label)

        # 索引统计信息
        self.index_stats_label = QLabel("")
        if index_status.get('status') == '已初始化':
            stats_text = f"包含 {index_status.get('file_count', 0)} 个文件"
            self.index_stats_label.setText(stats_text)
        status_layout.addWidget(self.index_stats_label)

        layout.addWidget(status_group)

        # 添加弹性空间
        layout.addStretch()

    def setup_rag_tab(self):
        """设置RAG构建选项卡"""
        layout = QVBoxLayout(self.rag_tab)

        # 文件选择区域
        file_group = QGroupBox("文档管理")
        file_layout = QVBoxLayout(file_group)

        # 单文件上传
        single_file_layout = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("选择文件...")
        single_file_layout.addWidget(self.file_path_input)

        self.browse_file_btn = QPushButton("浏览")
        self.browse_file_btn.clicked.connect(self.browse_file)
        single_file_layout.addWidget(self.browse_file_btn)

        self.add_file_btn = QPushButton("添加到RAG")
        self.add_file_btn.clicked.connect(self.add_file_to_rag)
        self.add_file_btn.setEnabled(bool(self.rag_builder))
        single_file_layout.addWidget(self.add_file_btn)

        file_layout.addLayout(single_file_layout)

        # 文件夹上传
        folder_layout = QHBoxLayout()
        self.folder_path_input = QLineEdit()
        self.folder_path_input.setPlaceholderText("选择文件夹...")
        folder_layout.addWidget(self.folder_path_input)

        self.browse_folder_btn = QPushButton("浏览")
        self.browse_folder_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.browse_folder_btn)

        self.add_folder_btn = QPushButton("添加到RAG")
        self.add_folder_btn.clicked.connect(self.add_folder_to_rag)
        self.add_folder_btn.setEnabled(bool(self.rag_builder))
        folder_layout.addWidget(self.add_folder_btn)

        file_layout.addLayout(folder_layout)

        # 最近文件列表
        recent_files_layout = QHBoxLayout()
        recent_files_layout.addWidget(QLabel("最近文件:"))

        self.recent_files_combo = QComboBox()
        recent_files = self.config_manager.get("recent_files", [])
        for file_path in recent_files:
            if os.path.exists(file_path):
                self.recent_files_combo.addItem(os.path.basename(file_path), file_path)

        if self.recent_files_combo.count() > 0:
            self.recent_files_combo.setCurrentIndex(0)
            self.file_path_input.setText(self.recent_files_combo.currentData())

        self.recent_files_combo.currentIndexChanged.connect(self.on_recent_file_selected)
        recent_files_layout.addWidget(self.recent_files_combo)

        file_layout.addLayout(recent_files_layout)
        layout.addWidget(file_group)

        # 索引管理区域
        index_group = QGroupBox("索引管理")
        index_layout = QVBoxLayout(index_group)

        # 保存/加载索引
        index_manage_layout = QHBoxLayout()
        self.save_index_btn = QPushButton("保存索引")
        self.save_index_btn.clicked.connect(self.save_index)
        self.save_index_btn.setEnabled(False)
        index_manage_layout.addWidget(self.save_index_btn)

        self.load_index_btn = QPushButton("加载索引")
        self.load_index_btn.clicked.connect(self.load_index_dialog)
        index_manage_layout.addWidget(self.load_index_btn)

        self.clear_index_btn = QPushButton("清空索引")
        self.clear_index_btn.clicked.connect(self.clear_index)
        self.clear_index_btn.setEnabled(False)
        index_manage_layout.addWidget(self.clear_index_btn)

        index_layout.addLayout(index_manage_layout)

        # 索引状态
        index_status = self.config_manager.get("index_status", {})
        status_text = f"索引状态: {index_status.get('status', '未初始化')}"
        if index_status.get('status') == '已初始化':
            status_text += f" ({index_status.get('document_count', 0)} 个文档片段)"

        self.index_status_label = QLabel(status_text)
        index_layout.addWidget(self.index_status_label)

        layout.addWidget(index_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 添加弹性空间
        layout.addStretch()

    def setup_verify_tab(self):
        """设置引用验证选项卡"""
        layout = QVBoxLayout(self.verify_tab)

        # 文本输入区域
        input_group = QGroupBox("文本输入")
        input_layout = QVBoxLayout(input_group)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("请输入要验证的文本内容...")
        input_layout.addWidget(self.text_input)

        # 按钮区域
        button_layout = QHBoxLayout()
        self.identify_btn = QPushButton("识别引用")
        self.identify_btn.clicked.connect(self.identify_citations)
        self.identify_btn.setEnabled(bool(self.rag_builder))
        button_layout.addWidget(self.identify_btn)

        self.validate_btn = QPushButton("验证引用")
        self.validate_btn.clicked.connect(self.validate_citations)
        self.validate_btn.setEnabled(bool(self.rag_builder and self.rag_builder.is_index_loaded()))
        button_layout.addWidget(self.validate_btn)

        input_layout.addLayout(button_layout)
        layout.addWidget(input_group)

        # 结果展示区域
        result_group = QGroupBox("验证结果")
        result_layout = QVBoxLayout(result_group)

        # 创建表格显示结果
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(6)
        self.result_table.setHorizontalHeaderLabels(["类型", "文件名称", "验证结果", "相似度", "方法", "详情"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        result_layout.addWidget(self.result_table)

        layout.addWidget(result_group)

        # 添加弹性空间
        layout.addStretch()

    def on_recent_file_selected(self, index):
        """最近文件选择变化"""
        if index >= 0:
            file_path = self.recent_files_combo.itemData(index)
            self.file_path_input.setText(file_path)

    def toggle_proxy_settings(self, state):
        """切换代理设置状态"""
        if state == Qt.Checked:
            self.proxy_input.setEnabled(True)
        else:
            self.proxy_input.setEnabled(False)

    def save_api_key(self):
        """保存API密钥和代理设置"""
        try:
            api_key = self.api_key_input.text().strip()
            if not api_key:
                QMessageBox.warning(self, "警告", "请输入有效的API密钥")
                return

            # 验证API密钥格式
            if not api_key.startswith("sk-") or len(api_key) < 20:
                QMessageBox.warning(self, "警告", "API密钥格式不正确")
                return

            self.api_key = api_key

            # 获取代理设置
            use_proxy = self.use_proxy_checkbox.isChecked()
            proxy_url = self.proxy_input.text().strip() if use_proxy else ""

            # 保存到配置
            self.config_manager.set("api_key", api_key)
            self.config_manager.set("use_proxy", use_proxy)
            self.config_manager.set("proxy_url", proxy_url)

            # 初始化RAG构建器和验证器
            try:
                self.rag_builder = RAGBuilder(self.api_key, use_proxy=use_proxy, proxy_url=proxy_url)
                self.citation_validator = CitationValidator(self.rag_builder)
                print("RAG构建器和验证器初始化成功")

                # 更新状态
                self.rag_status_label.setText("RAG索引: 已初始化")
            except Exception as e:
                print(f"初始化失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"初始化失败: {str(e)}")
                return

            # 更新UI状态
            self.api_status_label.setText("API密钥: 已设置")
            self.add_file_btn.setEnabled(True)
            self.add_folder_btn.setEnabled(True)
            self.identify_btn.setEnabled(True)

            QMessageBox.information(self, "成功", "API密钥已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存API密钥时出错: {str(e)}")

    def browse_file(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "",
            "文档文件 (*.pdf *.docx *.txt);;所有文件 (*)"
        )
        if file_path:
            self.file_path_input.setText(file_path)
            self.config_manager.add_recent_file(file_path)
            self.update_recent_files_combo()

    def browse_folder(self):
        """浏览文件夹"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder_path:
            self.folder_path_input.setText(folder_path)

    def update_recent_files_combo(self):
        """更新最近文件组合框"""
        self.recent_files_combo.clear()
        recent_files = self.config_manager.get("recent_files", [])
        for file_path in recent_files:
            if os.path.exists(file_path):
                self.recent_files_combo.addItem(os.path.basename(file_path), file_path)

    def add_file_to_rag(self):
        """添加文件到RAG"""
        if not self.rag_builder:
            QMessageBox.warning(self, "警告", "请先设置API密钥")
            return

        file_path = self.file_path_input.text()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "警告", "请选择有效的文件")
            return

        # 添加到最近文件列表
        self.config_manager.add_recent_file(file_path)
        self.update_recent_files_combo()

        # 创建工作线程
        self.worker = WorkerThread(self.rag_builder.add_document, file_path)
        self.worker.finished.connect(self.on_add_document_finished)
        self.worker.error.connect(self.on_worker_error)

        self.progress_bar.setVisible(True)
        self.statusBar().showMessage("正在添加文档到RAG...")
        self.worker.start()

    def add_folder_to_rag(self):
        """添加文件夹到RAG"""
        if not self.rag_builder:
            QMessageBox.warning(self, "警告", "请先设置API密钥")
            return

        folder_path = self.folder_path_input.text()
        if not folder_path or not os.path.exists(folder_path):
            QMessageBox.warning(self, "警告", "请选择有效的文件夹")
            return

        # 创建工作线程
        self.worker = WorkerThread(self.rag_builder.add_documents_from_folder, folder_path)
        self.worker.finished.connect(self.on_add_documents_finished)
        self.worker.error.connect(self.on_worker_error)

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.statusBar().showMessage("正在添加文件夹中的文档到RAG...")
        self.worker.start()

    def save_index(self):
        """保存索引"""
        if not self.rag_builder or not self.rag_builder.index:
            QMessageBox.warning(self, "警告", "没有可保存的索引")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存索引", self.current_index_path or "", "索引文件 (*.index)"
        )
        if file_path:
            # 移除可能的扩展名
            if file_path.endswith('.index'):
                file_path = file_path[:-6]

            try:
                success = self.rag_builder.save_index(file_path)
                if success:
                    self.current_index_path = file_path
                    self.config_manager.set("last_index_path", file_path)

                    # 更新配置中的索引状态
                    index_status = self.rag_builder.get_index_status()
                    self.config_manager.update_index_status(index_status)

                    QMessageBox.information(self, "成功", "索引已保存")
                    self.update_index_status()
                else:
                    QMessageBox.critical(self, "错误", "保存索引失败")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存索引失败: {str(e)}")

    def load_index_dialog(self):
        """加载索引对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "加载索引", self.current_index_path or "", "索引文件 (*.index)"
        )
        if file_path:
            # 移除可能的扩展名
            if file_path.endswith('.index'):
                file_path = file_path[:-6]
            self.load_index(file_path)

    def load_index(self, file_path: str, show_message: bool = True) -> bool:
        """加载索引"""
        if not os.path.exists(file_path + ".index") or not os.path.exists(file_path + ".json"):
            if show_message:
                QMessageBox.warning(self, "警告", "索引文件不完整")
            return False

        try:
            if not self.rag_builder:
                # 如果没有RAG构建器，先创建一个
                use_proxy = self.config_manager.get("use_proxy", False)
                proxy_url = self.config_manager.get("proxy_url", "")
                api_key = self.config_manager.get("api_key", "")

                if not api_key:
                    if show_message:
                        QMessageBox.warning(self, "警告", "请先设置API密钥")
                    return False

                self.rag_builder = RAGBuilder(api_key, use_proxy=use_proxy, proxy_url=proxy_url)
                self.citation_validator = CitationValidator(self.rag_builder)

            success = self.rag_builder.load_index(file_path)
            if success:
                self.current_index_path = file_path
                self.config_manager.set("last_index_path", file_path)

                # 更新配置中的索引状态
                index_status = self.rag_builder.get_index_status()
                self.config_manager.update_index_status(index_status)

                if show_message:
                    QMessageBox.information(self, "成功", "索引已加载")

                self.update_index_status()
                self.validate_btn.setEnabled(True)
                return True
            else:
                if show_message:
                    QMessageBox.critical(self, "错误", "加载索引失败")
                return False
        except Exception as e:
            print(f"加载索引时发生异常: {str(e)}")
            if show_message:
                QMessageBox.critical(self, "错误", f"加载索引时发生异常: {str(e)}")
            # 重置索引状态
            self.current_index_path = ""
            self.config_manager.set("last_index_path", "")
            self.rag_builder = RAGBuilder(self.api_key) if self.api_key else None
            self.citation_validator = CitationValidator(self.rag_builder) if self.rag_builder else None
            self.update_index_status()
            return False

    def clear_index(self):
        """清空索引"""
        if not self.rag_builder:
            return

        reply = QMessageBox.question(self, "确认", "确定要清空索引吗？此操作不可撤销。",
                                     QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.rag_builder.clear_index()
            self.current_index_path = ""
            self.config_manager.set("last_index_path", "")

            # 更新配置中的索引状态
            self.config_manager.update_index_status({
                "status": "未初始化",
                "document_count": 0,
                "file_count": 0,
                "dimension": 0
            })

            self.update_index_status()
            self.validate_btn.setEnabled(False)
            QMessageBox.information(self, "成功", "索引已清空")

    def update_index_status(self):
        """更新索引状态显示"""
        if not self.rag_builder:
            self.index_status_label.setText("索引状态: 未初始化")
            self.index_stats_label.setText("")
            self.rag_status_label.setText("RAG索引: 未初始化")
            return

        status = self.rag_builder.get_index_status()

        if status["status"] == "未初始化":
            self.index_status_label.setText("索引状态: 未初始化")
            self.index_stats_label.setText("")
            self.rag_status_label.setText("RAG索引: 未初始化")
            self.save_index_btn.setEnabled(False)
            self.clear_index_btn.setEnabled(False)
            self.validate_btn.setEnabled(False)
        else:
            self.index_status_label.setText(f"索引状态: 已初始化 ({status['document_count']} 个文档片段)")
            self.rag_status_label.setText(f"RAG索引: 已初始化 ({status['document_count']} 个文档片段)")

            # 显示文件统计信息
            stats_text = f"包含 {status['file_count']} 个文件"
            self.index_stats_label.setText(stats_text)

            self.save_index_btn.setEnabled(True)
            self.clear_index_btn.setEnabled(True)
            self.validate_btn.setEnabled(True)

    def identify_citations(self):
        """识别引用"""
        text = self.text_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "警告", "请输入要识别的文本")
            return

        # 限制文本长度，避免内存溢出
        if len(text) > 10000:
            text = text[:10000]
            QMessageBox.warning(self, "提示", "文本过长，已截取前10000个字符进行处理")

        # 创建工作线程
        self.worker = WorkerThread(self.citation_identifier.identify_citations, self.api_key, text)
        self.worker.finished.connect(self.on_identify_citations_finished)
        self.worker.error.connect(self.on_worker_error)

        self.progress_bar.setVisible(True)
        self.statusBar().showMessage("正在识别引用...")
        self.worker.start()

    def validate_citations(self):
        """验证引用"""
        if not hasattr(self, 'current_citations') or not self.current_citations:
            QMessageBox.warning(self, "警告", "请先识别引用")
            return

        if not self.rag_builder or not self.rag_builder.is_index_loaded():
            QMessageBox.warning(self, "警告", "请先构建或加载RAG索引")
            return

        # 创建工作线程
        self.worker = WorkerThread(self.citation_validator.validate_with_rag, self.current_citations)
        self.worker.finished.connect(self.on_validate_citations_finished)
        self.worker.error.connect(self.on_worker_error)

        self.progress_bar.setVisible(True)
        self.statusBar().showMessage("正在验证引用...")
        self.worker.start()

    def on_add_document_finished(self, result):
        """添加文档完成"""
        self.progress_bar.setVisible(False)

        # 更新索引状态
        self.update_index_status()

        self.statusBar().showMessage(f"文档已添加到RAG: {result['chunk_count']} 个片段")
        QMessageBox.information(self, "成功",
                                f"文档已成功添加到RAG\n新增 {result['chunk_count']} 个文档片段\n总计 {result['total_chunks']} 个文档片段")

    def on_add_documents_finished(self, results):
        """添加文件夹完成"""
        self.progress_bar.setVisible(False)

        # 统计结果
        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = sum(1 for r in results if r["status"] == "error")

        # 更新索引状态
        self.update_index_status()

        self.statusBar().showMessage(f"文件夹处理完成: {success_count} 成功, {error_count} 失败")

        if error_count > 0:
            error_files = [r["file_path"] for r in results if r["status"] == "error"]
            error_msg = f"成功处理 {success_count} 个文件，失败 {error_count} 个文件\n\n失败的文件:\n" + "\n".join(
                error_files[:5])
            if len(error_files) > 5:
                error_msg += f"\n... 以及另外 {len(error_files) - 5} 个文件"

            QMessageBox.warning(self, "部分成功", error_msg)
        else:
            QMessageBox.information(self, "成功", f"所有 {success_count} 个文件已成功添加到RAG")

    def on_identify_citations_finished(self, citations):
        """识别引用完成"""
        self.progress_bar.setVisible(False)
        self.current_citations = citations

        # 显示识别结果
        self.result_table.setRowCount(len(citations))
        for i, citation in enumerate(citations):
            self.result_table.setItem(i, 0, QTableWidgetItem(citation.get("type", "")))
            self.result_table.setItem(i, 1, QTableWidgetItem(citation.get("title", "")))
            self.result_table.setItem(i, 2, QTableWidgetItem("待验证"))
            self.result_table.setItem(i, 3, QTableWidgetItem(""))
            self.result_table.setItem(i, 4, QTableWidgetItem(citation.get("method", "")))

            # 详情按钮
            detail_btn = QPushButton("查看详情")
            detail_btn.clicked.connect(lambda checked, idx=i: self.show_citation_detail(idx))
            self.result_table.setCellWidget(i, 5, detail_btn)

        self.statusBar().showMessage(f"识别到 {len(citations)} 个引用")

    def on_validate_citations_finished(self, validated_citations):
        """验证引用完成"""
        self.progress_bar.setVisible(False)
        self.current_citations = validated_citations

        # 显示验证结果
        self.result_table.setRowCount(len(validated_citations))
        for i, citation in enumerate(validated_citations):
            self.result_table.setItem(i, 0, QTableWidgetItem(citation.get("type", "")))
            self.result_table.setItem(i, 1, QTableWidgetItem(citation.get("title", "")))

            # 验证结果
            if citation.get("validated", False):
                result_text = "验证通过"
                score = min(citation.get("similarity_scores", [1.0])) if citation.get("similarity_scores") else "N/A"
                if isinstance(score, float):
                    score = f"{score:.4f}"
            else:
                result_text = "验证失败"
                score = "N/A"

            self.result_table.setItem(i, 2, QTableWidgetItem(result_text))
            self.result_table.setItem(i, 3, QTableWidgetItem(str(score)))
            self.result_table.setItem(i, 4, QTableWidgetItem(citation.get("method", "")))

            # 详情按钮
            detail_btn = QPushButton("查看详情")
            detail_btn.clicked.connect(lambda checked, idx=i: self.show_citation_detail(idx))
            self.result_table.setCellWidget(i, 5, detail_btn)

        # 统计验证结果
        validated_count = sum(1 for c in validated_citations if c.get("validated", False))
        total_count = len(validated_citations)
        validation_rate = validated_count / total_count * 100 if total_count > 0 else 0

        self.statusBar().showMessage(f"验证完成: {validated_count}/{total_count} 通过 ({validation_rate:.1f}%)")

    def show_citation_detail(self, index):
        """显示引用详情"""
        if index < len(self.current_citations):
            citation = self.current_citations[index]

            detail_text = f"""
            引用类型: {citation.get('type', '未知')}
            文件名称: {citation.get('title', '未知')}
            引用内容: {citation.get('content', '未知')}
            识别方法: {citation.get('method', '未知')}
            """

            if 'validated' in citation:
                detail_text += f"\n验证结果: {'通过' if citation['validated'] else '失败'}"

                if citation.get('validated', False) and 'rag_results' in citation:
                    detail_text += "\n\n相关文档:\n"
                    for i, result in enumerate(citation['rag_results']):
                        detail_text += f"\n{i + 1}. {result['document'][:100]}...\n   相似度: {result['score']:.4f}\n"

            QMessageBox.information(self, "引用详情", detail_text)

    def on_worker_error(self, error_msg):
        """工作线程错误处理"""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "错误", f"操作失败: {error_msg}")
        self.statusBar().showMessage("操作失败")

    def closeEvent(self, event):
        """程序关闭事件"""
        # 保存当前配置
        if self.rag_builder and self.rag_builder.is_index_loaded():
            # 更新索引状态到配置
            index_status = self.rag_builder.get_index_status()
            self.config_manager.update_index_status(index_status)

        self.config_manager.save_config()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = RAGFrontend()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()