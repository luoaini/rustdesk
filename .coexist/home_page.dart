import 'package:flutter/material.dart';
import 'package:flutter_hbb/mobile/pages/server_page.dart';
import 'package:flutter_hbb/mobile/pages/settings_page.dart';
import 'package:flutter_hbb/web/settings_page.dart';
import 'package:get/get.dart';
import '../../common.dart';
import '../../models/platform_model.dart';
import '../../models/state_model.dart';
import 'connection_page.dart';

/// 本地选项键：当前模式。
/// control = 控制端（默认，主页为远程控制列表）；share = 被控端
const kOptionCoexistMode = 'coexist-mode';

/// 读取当前模式。除 share 外一律按 control 处理，保证老配置平滑升级。
String get coexistMode {
  if (isWeb) return 'control';
  try {
    final v = bind.mainGetLocalOption(key: kOptionCoexistMode);
    if (v == 'share') return 'share';
  } catch (_) {}
  return 'control';
}

/// 切换模式并落盘，同时让主页立即重建。
Future<void> setCoexistMode(String mode) async {
  await bind.mainSetLocalOption(
      key: kOptionCoexistMode, value: mode == 'share' ? 'share' : 'control');
  HomePage.homeKey.currentState?.refreshPages();
}

abstract class PageShape extends Widget {
  final String title = "";
  final Widget icon = Icon(null);
  final List<Widget> appBarActions = [];
}

class HomePage extends StatefulWidget {
  static final homeKey = GlobalKey<HomePageState>();

  HomePage() : super(key: homeKey);

  @override
  HomePageState createState() => HomePageState();
}

class HomePageState extends State<HomePage> {
  int _selectedIndex = 0;
  int get selectedIndex => _selectedIndex;
  final List<PageShape> _pages = [];

  /// 单人模式不再有聊天 Tab，保持该接口恒为 false，
  /// 以便 chat_model 等处的既有判断安全退化。
  bool get isChatPageCurrentTab => false;

  void refreshPages() {
    if (!mounted) {
      initPages();
      return;
    }
    setState(() {
      initPages();
    });
  }

  @override
  void initState() {
    super.initState();
    initPages();
  }

  /// 按当前模式只装载一个页面：
  /// 控制端 -> 远程控制列表（ConnectionPage）；被控端 -> 本机共享页（ServerPage）
  void initPages() {
    _pages.clear();
    if (coexistMode == 'share') {
      if (isAndroid && !bind.isOutgoingOnly()) {
        _pages.add(ServerPage());
      }
    } else {
      if (!bind.isIncomingOnly()) {
        _pages.add(ConnectionPage(appBarActions: []));
      }
    }
    if (_pages.isEmpty) {
      _pages.add(ConnectionPage(appBarActions: []));
    }
    _selectedIndex = 0;
  }

  String get _title {
    if (coexistMode == 'share') return '被控端';
    return '远程控制';
  }

  @override
  Widget build(BuildContext context) {
    final page = _pages[_selectedIndex.clamp(0, _pages.length - 1)];
    return WillPopScope(
        onWillPop: () async {
          return true;
        },
        child: Scaffold(
          appBar: AppBar(
            centerTitle: true,
            title: Text(_title),
            // 右上角唯一入口：设置
            actions: [
              IconButton(
                tooltip: '设置',
                icon: const Icon(Icons.settings),
                onPressed: () => _openSettings(context),
              ),
            ],
          ),
          body: page,
        ));
  }

  /// 以整页路由打开设置页（设置页自身只返回 SettingsList，需要外层 Scaffold）
  void _openSettings(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) {
      return Scaffold(
        appBar: AppBar(
          centerTitle: true,
          title: const Text('设置'),
        ),
        body: SettingsPage(),
      );
    }));
  }
}

class WebHomePage extends StatelessWidget {
  final connectionPage =
      ConnectionPage(appBarActions: <Widget>[const WebSettingsPage()]);

  @override
  Widget build(BuildContext context) {
    stateGlobal.isInMainPage = true;
    handleUnilink(context);
    return Scaffold(
      // backgroundColor: MyTheme.grayBg,
      appBar: AppBar(
        centerTitle: true,
        title: Text("${bind.mainGetAppNameSync()} (Preview)"),
        actions: connectionPage.appBarActions,
      ),
      body: connectionPage,
    );
  }

  handleUnilink(BuildContext context) {
    if (webInitialLink.isEmpty) {
      return;
    }
    final link = webInitialLink;
    webInitialLink = '';
    final splitter = ["/#/", "/#", "#/", "#"];
    var fakelink = '';
    for (var s in splitter) {
      if (link.contains(s)) {
        var list = link.split(s);
        if (list.length < 2 || list[1].isEmpty) {
          return;
        }
        list.removeAt(0);
        fakelink = "rustdesk://${list.join(s)}";
        break;
      }
    }
    if (fakelink.isEmpty) {
      return;
    }
    final uri = Uri.tryParse(fakelink);
    if (uri == null) {
      return;
    }
    final args = urlLinkToCmdArgs(uri);
    if (args == null || args.isEmpty) {
      return;
    }
    bool isFileTransfer = false;
    bool isViewCamera = false;
    bool isTerminal = false;
    String? id;
    String? password;
    var loginMethod = '';
    for (int i = 0; i < args.length; i++) {
      switch (args[i]) {
        case '--connect':
        case '--play':
          id = args[i + 1];
          i++;
          break;
        case '--file-transfer':
          isFileTransfer = true;
          id = args[i + 1];
          i++;
          break;
        case '--view-camera':
          isViewCamera = true;
          id = args[i + 1];
          i++;
          break;
        case '--terminal':
          isTerminal = true;
          id = args[i + 1];
          i++;
          break;
        case '--terminal-admin':
          setEnvTerminalAdmin();
          isTerminal = true;
          id = args[i + 1];
          i++;
          break;
        case '--password':
          password = args[i + 1];
          i++;
          break;
        case '--request-approval':
          loginMethod = 'request-approval';
          break;
        default:
          break;
      }
    }
    if (id != null) {
      connect(context, id,
          isFileTransfer: isFileTransfer,
          isViewCamera: isViewCamera,
          isTerminal: isTerminal,
          loginMethod: loginMethod,
          password: password);
    }
  }
}
