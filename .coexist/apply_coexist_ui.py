#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RustDesk 共存版「单界面 + 主页权限总控」一键补丁

用法:
    python3 apply_coexist_ui.py /path/to/rustdesk [--version-code 73]

改动内容:
    1. flutter/lib/mobile/pages/home_page.dart   -> 单界面版（右上角仅一个设置按钮）
    2. flutter/lib/mobile/pages/settings_page.dart -> 设置页顶部插入「主页形态」切换项
    3. flutter/lib/mobile/pages/server_page.dart -> 被控端主页「权限」区块补齐系统权限：
       开机自启 / 电池优化豁免 / 悬浮窗，全部就地开关，不必再进设置页
    4. flutter/android/app/build.gradle          -> applicationId 改 com.remotehelp.coexist，versionCode 可控
    5. flutter/android/app/src/main/AndroidManifest.xml -> 应用名改「远程协助」/「远程协助输入」
    6. flutter/android/key.properties + app/coexist.jks -> 内置签名，可覆盖升级已装的共存版
幂等：重复执行不会重复插入。
"""
import base64
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_HOME = os.path.join(HERE, "home_page.dart")
KS_B64 = os.path.join(HERE, "coexist_jks.b64")

APP_ID_OLD = 'applicationId "com.carriez.flutter_hbb"'
APP_ID_NEW = 'applicationId "com.remotehelp.coexist"'
VC_OLD = "versionCode flutterVersionCode.toInteger()"

ANCHOR = "      sections: [\n        customClientSection,\n"
SECTION = """      sections: [
        customClientSection,
        SettingsSection(
          title: const Text('远程协助'),
          tiles: [
            SettingsTile(
              title: Text(coexistMode == 'share'
                  ? '主页形态：共享屏幕（被控端）'
                  : '主页形态：连接（控制端）'),
              description: const Text('点击切换，返回主页后界面随之变化'),
              leading: const Icon(Icons.swap_horiz),
              onPressed: (context) async {
                await setCoexistMode(
                    coexistMode == 'share' ? 'control' : 'share');
                if (mounted) setState(() {});
              },
            ),
          ],
        ),
"""

# ---------- server_page.dart：主页权限总控 ----------
SP_STATE_ANCHOR = """class _PermissionCheckerState extends State<PermissionChecker> {
  static const _folderOptionIndent = 16.0;
"""

SP_STATE_ADD = """class _PermissionCheckerState extends State<PermissionChecker> {
  static const _folderOptionIndent = 16.0;

  // ===== coexist patch: 主页权限总控 =====
  bool _startOnBoot = false;
  bool _ignoreBatteryOpt = false;
  bool _floatingWindowOk = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _refreshSysPerms();
    });
  }

  Future<void> _refreshSysPerms() async {
    if (!isAndroid) return;
    var s = false, b = false, f = false;
    try {
      s = (await gFFI.invokeMethod(AndroidChannel.kGetStartOnBootOpt)) == true;
    } catch (_) {}
    try {
      b = await AndroidPermissionManager.check(
          kRequestIgnoreBatteryOptimizations);
    } catch (_) {}
    try {
      f = await AndroidPermissionManager.check(kSystemAlertWindow);
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _startOnBoot = s;
      _ignoreBatteryOpt = b;
      _floatingWindowOk = f;
    });
  }

  Future<void> _toggleStartOnBoot(bool v) async {
    if (v) {
      if (!await AndroidPermissionManager.check(
          kRequestIgnoreBatteryOptimizations)) {
        if (!await AndroidPermissionManager.request(
            kRequestIgnoreBatteryOptimizations)) return;
      }
      if (!await AndroidPermissionManager.check(kSystemAlertWindow)) {
        if (!await AndroidPermissionManager.request(kSystemAlertWindow)) {
          return;
        }
      }
    }
    gFFI.invokeMethod(AndroidChannel.kSetStartOnBootOpt, v);
    if (mounted) setState(() => _startOnBoot = v);
    await _refreshSysPerms();
  }

  Future<void> _toggleIgnoreBattery(bool v) async {
    if (v) {
      await AndroidPermissionManager.request(
          kRequestIgnoreBatteryOptimizations);
    } else {
      AndroidPermissionManager.startAction(kActionApplicationDetailsSettings);
    }
    await Future.delayed(const Duration(milliseconds: 800));
    await _refreshSysPerms();
  }

  Future<void> _toggleFloatingWindow(bool v) async {
    if (v) {
      if (!await AndroidPermissionManager.check(kSystemAlertWindow)) {
        if (!await AndroidPermissionManager.request(kSystemAlertWindow)) {
          return;
        }
      }
    }
    bind.mainSetLocalOption(
        key: kOptionDisableFloatingWindow, value: v ? 'N' : 'Y');
    gFFI.serverModel.androidUpdatekeepScreenOn();
    await _refreshSysPerms();
  }
  // ===== coexist patch end =====
"""

SP_UI_ANCHOR = """          PermissionRow(
            translate("Enable clipboard"),
            serverModel.clipboardOk,
            serverModel.toggleClipboard,
            enabled: !permissionChangeLocked,
          ),
        ]));
"""

SP_UI_ADD = """          PermissionRow(
            translate("Enable clipboard"),
            serverModel.clipboardOk,
            serverModel.toggleClipboard,
            enabled: !permissionChangeLocked,
          ),
          if (isAndroid) ...[
            const Divider(height: 18),
            Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: Text('系统权限',
                  style: const TextStyle(
                      fontSize: 12, color: MyTheme.darkGray)),
            ),
            SwitchListTile(
              visualDensity: VisualDensity.compact,
              contentPadding: EdgeInsets.zero,
              title: Text(translate('Start on boot')),
              subtitle: const Text('开机自动把共享服务拉起来',
                  style: TextStyle(fontSize: 11, color: MyTheme.darkGray)),
              value: _startOnBoot,
              onChanged: _toggleStartOnBoot,
            ),
            SwitchListTile(
              visualDensity: VisualDensity.compact,
              contentPadding: EdgeInsets.zero,
              title: Text(translate('Ignore Battery Optimizations')),
              subtitle: const Text('不豁免容易被系统杀后台',
                  style: TextStyle(fontSize: 11, color: MyTheme.darkGray)),
              value: _ignoreBatteryOpt,
              onChanged: _toggleIgnoreBattery,
            ),
            SwitchListTile(
              visualDensity: VisualDensity.compact,
              contentPadding: EdgeInsets.zero,
              title: Text(translate('Floating window')),
              subtitle: const Text('悬浮窗权限，常亮与保活依赖它',
                  style: TextStyle(fontSize: 11, color: MyTheme.darkGray)),
              value: _floatingWindowOk,
              onChanged: _toggleFloatingWindow,
            ),
          ],
        ]));
"""


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def patch_home(root):
    home = os.path.join(root, "flutter/lib/mobile/pages/home_page.dart")
    bak = home + ".orig"
    if not os.path.exists(bak):
        shutil.copy2(home, bak)
    shutil.copy2(NEW_HOME, home)
    print("[ok] home_page.dart -> 单界面版")


def patch_settings(root):
    p = os.path.join(root, "flutter/lib/mobile/pages/settings_page.dart")
    src = read(p)
    if "kOptionCoexistMode" in src or "主页形态" in src:
        print("[skip] settings_page.dart 已含切换项")
        return
    if src.count(ANCHOR) != 1:
        raise SystemExit("[fail] settings_page.dart 锚点异常，需人工处理")
    bak = p + ".orig"
    if not os.path.exists(bak):
        shutil.copy2(p, bak)
    write(p, src.replace(ANCHOR, SECTION, 1))
    print("[ok] settings_page.dart -> 已插入「主页形态」切换项")


def patch_server_perms(root):
    p = os.path.join(root, "flutter/lib/mobile/pages/server_page.dart")
    src = read(p)
    if "coexist patch: 主页权限总控" in src:
        print("[skip] server_page.dart 已含主页权限总控")
        return
    if src.count(SP_STATE_ANCHOR) != 1:
        raise SystemExit("[fail] server_page.dart 状态锚点异常，需人工处理")
    if src.count(SP_UI_ANCHOR) != 1:
        raise SystemExit("[fail] server_page.dart UI 锚点异常，需人工处理")
    bak = p + ".orig"
    if not os.path.exists(bak):
        shutil.copy2(p, bak)
    src = src.replace(SP_STATE_ANCHOR, SP_STATE_ADD, 1)
    src = src.replace(SP_UI_ANCHOR, SP_UI_ADD, 1)
    write(p, src)
    print("[ok] server_page.dart -> 主页权限区块已补齐（自启动/电池豁免/悬浮窗）")


def patch_gradle(root, version_code):
    p = os.path.join(root, "flutter/android/app/build.gradle")
    src = read(p)
    if APP_ID_NEW not in src:
        if APP_ID_OLD not in src:
            raise SystemExit("[fail] build.gradle 找不到 applicationId，需人工处理")
        src = src.replace(APP_ID_OLD, APP_ID_NEW, 1)
        print("[ok] build.gradle -> applicationId 改为 com.remotehelp.coexist")
    if VC_OLD in src:
        src = src.replace(VC_OLD, "versionCode %d" % version_code, 1)
        print("[ok] build.gradle -> versionCode 固定为 %d" % version_code)
    write(p, src)


def patch_manifest(root):
    p = os.path.join(root, "flutter/android/app/src/main/AndroidManifest.xml")
    src = read(p)
    n = 0
    if 'android:label="RustDesk Input"' in src:
        src = src.replace('android:label="RustDesk Input"', 'android:label="远程协助输入"')
        n += 1
    if 'android:label="RustDesk"' in src:
        src = src.replace('android:label="RustDesk"', 'android:label="远程协助"')
        n += 1
    write(p, src)
    print("[ok] AndroidManifest.xml -> 应用名改动 %d 处" % n)


def setup_signing(root):
    and_dir = os.path.join(root, "flutter/android")
    app_dir = os.path.join(and_dir, "app")
    props = os.path.join(and_dir, "key.properties")
    ks = os.path.join(app_dir, "coexist.jks")
    write(props, "storePassword=rdc123456\nkeyPassword=rdc123456\n"
                 "keyAlias=rdc\nstoreFile=coexist.jks\n")
    with open(KS_B64, "r", encoding="utf-8") as f:
        data = base64.b64decode(f.read().strip())
    with open(ks, "wb") as f:
        f.write(data)
    print("[ok] 内置签名 coexist.jks + key.properties")


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        return 1
    root = os.path.abspath(args[0])
    vc = 73
    if "--version-code" in args:
        vc = int(args[args.index("--version-code") + 1])
    if not os.path.isdir(os.path.join(root, "flutter")):
        raise SystemExit("[fail] %s 看起来不是 rustdesk 源码根目录" % root)
    patch_home(root)
    patch_settings(root)
    patch_server_perms(root)
    patch_gradle(root, vc)
    patch_manifest(root)
    setup_signing(root)
    print("[done] 补丁应用完成，可以直接 flutter build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
