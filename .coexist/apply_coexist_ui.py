#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
「远程控制」单界面 App 一键补丁（启动即远程控制列表 + 设置页切换控制端/被控端）

用法:
    python3 apply_coexist_ui.py /path/to/rustdesk [--version-code 72]

改动内容:
    1. flutter/lib/mobile/pages/home_page.dart   -> 单界面版（控制端=远程控制列表，右上角仅一个设置按钮）
    2. flutter/lib/mobile/pages/settings_page.dart -> 设置页顶部插入「模式：控制端/被控端」切换项
    3. flutter/android/app/build.gradle          -> applicationId 保持 com.remotehelp.coexist（覆盖升级），versionCode 可控
    4. flutter/android/app/src/main/AndroidManifest.xml -> 应用名改「远程控制」/「远程控制输入」
    5. flutter/android/key.properties + app/coexist.jks -> 内置签名
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
APP_ID_NEW = 'applicationId "com.remotehelp.coexist"'  # 沿用旧包名，覆盖升级上一版
VC_OLD = "versionCode flutterVersionCode.toInteger()"

ANCHOR = "      sections: [\n        customClientSection,\n"
SECTION = """      sections: [
        customClientSection,
        SettingsSection(
          title: const Text('远程控制'),
          tiles: [
            SettingsTile(
              title: Text(coexistMode == 'share'
                  ? '当前模式：被控端（本机可被控制）'
                  : '当前模式：控制端（远程控制别人）'),
              description: const Text('点击切换，返回主页即为对应界面'),
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
    print("[ok] home_page.dart -> 单界面版（控制端=远程控制列表）")


def patch_settings(root):
    p = os.path.join(root, "flutter/lib/mobile/pages/settings_page.dart")
    src = read(p)
    if "kOptionCoexistMode" in src or "当前模式" in src:
        print("[skip] settings_page.dart 已含切换项")
        return
    if src.count(ANCHOR) != 1:
        raise SystemExit("[fail] settings_page.dart 锚点异常，需人工处理")
    bak = p + ".orig"
    if not os.path.exists(bak):
        shutil.copy2(p, bak)
    write(p, src.replace(ANCHOR, SECTION, 1))
    print("[ok] settings_page.dart -> 已插入「主页形态」切换项")


def patch_gradle(root, version_code):
    p = os.path.join(root, "flutter/android/app/build.gradle")
    src = read(p)
    if APP_ID_NEW not in src:
        if APP_ID_OLD not in src:
            raise SystemExit("[fail] build.gradle 找不到 applicationId，需人工处理")
        src = src.replace(APP_ID_OLD, APP_ID_NEW, 1)
        print("[ok] build.gradle -> applicationId 保持 com.remotehelp.coexist（覆盖升级）")
    if VC_OLD in src:
        src = src.replace(VC_OLD, "versionCode %d" % version_code, 1)
        print("[ok] build.gradle -> versionCode 固定为 %d" % version_code)
    write(p, src)


def patch_manifest(root):
    p = os.path.join(root, "flutter/android/app/src/main/AndroidManifest.xml")
    src = read(p)
    n = 0
    if 'android:label="RustDesk Input"' in src:
        src = src.replace('android:label="RustDesk Input"', 'android:label="远程控制输入"')
        n += 1
    if 'android:label="RustDesk"' in src:
        src = src.replace('android:label="RustDesk"', 'android:label="远程控制"')
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
    vc = 72
    if "--version-code" in args:
        vc = int(args[args.index("--version-code") + 1])
    if not os.path.isdir(os.path.join(root, "flutter")):
        raise SystemExit("[fail] %s 看起来不是 rustdesk 源码根目录" % root)
    patch_home(root)
    patch_settings(root)
    patch_gradle(root, vc)
    patch_manifest(root)
    setup_signing(root)
    print("[done] 补丁应用完成，可以直接 flutter build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
