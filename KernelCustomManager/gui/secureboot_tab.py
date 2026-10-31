"""
Onglet de gestion SecureBoot
Diagnostic, statut, clés MOK, signature des modules et de vmlinuz, historique
"""

import logging
import os
import re
import subprocess
from datetime import datetime

from gi.repository import GLib, Gtk

from gui.widgets import (button, button_row, clear_box, entry, info_bar, inner_tabs, labeled,
                         markup_label, monospace_view, page_box, run_once_when_mapped, section)
from utils.dialogs import run_task
from utils.i18n import get_i18n
from utils.pkexec_helper import PkexecHelper
from utils.terminal import launch_in_terminal

esc = GLib.markup_escape_text

KEY_FILTERS_PATTERNS = ["*.der", "*.cer", "*.crt", "*.pem", "*.priv", "*.key"]


class SecureBootPage:
    """État et widgets de l'onglet SecureBoot"""

    def __init__(self, main_window):
        self.win = main_window
        self.dialogs = main_window.dialogs
        self.i18n = get_i18n()
        self.sb = main_window.secureboot_manager

    # ==================== Construction ====================

    def build(self):
        i18n = self.i18n
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(self._build_info_bar())

        tabs, _stack = inner_tabs([
            ("wizard", "🚀 " + i18n._("secureboot.tab_wizard"), self._build_wizard()),
            ("status", i18n._("secureboot.tab_status"), self._build_status()),
            ("keys", i18n._("secureboot.tab_keys"), self._build_keys()),
            ("signing", i18n._("secureboot.tab_signing"), self._build_signing()),
            ("history", i18n._("secureboot.tab_history"), self._build_history()),
        ])
        root.append(tabs)

        # Le diagnostic et la liste des clés MOK passent par pkexec (mot de passe) :
        # on attend que l'utilisateur ouvre l'onglet au lieu de les lancer au démarrage
        # (une seule lecture pkexec : la liste des clés réutilise le cache du diagnostic)
        run_once_when_mapped(root, lambda: self.run_diagnosis(clear_cache=False))

        self.update_history()
        return root

    def _build_info_bar(self):
        i18n = self.i18n
        enabled = f"<span color='green'>{i18n._('secureboot.enabled')}</span>"
        if not self.sb.is_uefi_system():
            return info_bar(f"<b>🔒 UEFI:</b> <span color='red'>{i18n._('secureboot.disabled')}</span>")

        status = self.sb.get_secureboot_status()
        items = [
            f"<b>🔒 UEFI:</b> {enabled}",
            f"<b>🛡️ SecureBoot:</b> " + (enabled if status['enabled'] else
                                         f"<span color='orange'>{i18n._('secureboot.disabled')}</span>"),
        ]
        if self.sb.check_setup_mode():
            items.append(f"<b>⚙️ {i18n._('secureboot.setup_mode')}:</b> "
                         f"<span color='orange'>{i18n._('secureboot.active')}</span>")
        return info_bar(*items)

    # ==================== Assistant ====================

    def _build_wizard(self):
        i18n = self.i18n
        box = page_box(spacing=16, margin=18)

        title = markup_label(f"<big><b>🔒 {i18n._('secureboot.wizard_title')}</b></big>")
        title.set_xalign(0.5)
        box.append(title)

        diagnosis, inner = section("📊 " + i18n._("secureboot.auto_diagnosis"))
        self.diagnosis_label = markup_label(f"<i>{i18n._('secureboot.diag_on_open')}</i>", selectable=True)
        inner.append(self.diagnosis_label)
        box.append(diagnosis)

        actions, self.actions_box = section("⚡ " + i18n._("secureboot.recommended_actions"))
        box.append(actions)

        self.diagnose_button = button("🔍 " + i18n._("secureboot.run_diagnosis"),
                                      lambda: self.run_diagnosis(clear_cache=True), "suggested-action")
        self.diagnose_button.set_halign(Gtk.Align.CENTER)
        self.diagnose_button.add_css_class("pill")
        box.append(self.diagnose_button)

        return Gtk.ScrolledWindow(child=box, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)

    def run_diagnosis(self, clear_cache=True):
        """Exécute le diagnostic (thread) et affiche les actions recommandées"""
        i18n = self.i18n
        clear_box(self.actions_box)
        self.diagnosis_label.set_markup(f"<i>{i18n._('secureboot.analyzing')}…</i>")
        self.diagnose_button.set_sensitive(False)

        def work():
            if clear_cache:
                self.sb.clear_mok_cache()  # état actuel (après un enrôlement, un redémarrage…)
            return self.sb.diagnose_secureboot_issue()

        def done(diag):
            self.diagnose_button.set_sensitive(True)
            self.display_diagnosis(diag)
            self.update_enrolled_keys()  # depuis le cache rempli par le diagnostic

        def failed(error):
            self.diagnose_button.set_sensitive(True)
            self.diagnosis_label.set_markup(f"<span color='red'>❌ {esc(str(error))}</span>")

        run_task(work, done, failed)

    def display_diagnosis(self, diag):
        issue = diag['issue_type']

        if issue == 'OK':
            self.diagnosis_label.set_markup(f"<span color='green'><b>✅ {esc(diag['message'])}</b></span>")
        elif issue in ('NOT_UEFI', 'SB_DISABLED'):
            self.diagnosis_label.set_markup(f"<span color='orange'><b>⚠️ {esc(diag['message'])}</b></span>")
        elif issue == 'KERNEL_SIGNATURE_ISSUES':
            icons = {'MODULES_UNSIGNED': ("📦", "Modules"), 'INITRD_UNSIGNED_MODULES': ("💾", "Initrd"),
                     'VMLINUZ_UNSIGNED': ("🔧", "vmlinuz")}
            lines = [f"<span color='red'><b>❌ {esc(self.i18n._('secureboot.signature_issues'))}</b></span>"]
            for kernel_info in diag.get('details', {}).get('kernels', []):
                lines.append(f"\n<b>Kernel {esc(kernel_info['kernel_version'])} :</b>")
                for problem in kernel_info['issues']:
                    icon, name = icons.get(problem['type'], ("•", ""))
                    lines.append(f"  {icon} {name}: {esc(problem['message'])}")
            self.diagnosis_label.set_markup('\n'.join(lines))
        else:
            self.diagnosis_label.set_markup(f"<span color='red'><b>❌ {esc(diag['message'])}</b></span>")

        # Solutions, avec un bouton d'action sur la première
        for index, solution in enumerate(diag['solutions'], 1):
            row = Gtk.Box(spacing=12)
            label = markup_label()
            label.set_text(f"{index}. {solution}")
            label.set_hexpand(True)
            row.append(label)

            if index == 1:
                action = None
                if issue == 'MOK_NOT_ENROLLED':
                    action = button("▶️ " + self.i18n._("secureboot.start_enrollment"), self.mok_enrollment_wizard,
                                    "suggested-action")
                elif issue == 'MOK_PENDING':
                    action = button("🔄 " + self.i18n._("button.reboot_now"), self.confirm_reboot)
                elif issue in ('MODULES_NOT_SIGNED', 'KERNEL_SIGNATURE_ISSUES'):
                    action = button("▶️ " + self.i18n._("secureboot.start_signing"), self.module_signing_wizard,
                                    "suggested-action")
                if action:
                    action.set_valign(Gtk.Align.CENTER)
                    row.append(action)

            self.actions_box.append(row)

    # ==================== Redémarrage ====================

    def reboot(self):
        def done(result):
            success, _, error = result
            if not success:
                self.dialogs.show_error(self.i18n._("message.error.title"), f"Reboot: {error}")
        run_task(PkexecHelper.reboot, done)

    def confirm_reboot(self):
        i18n = self.i18n
        self.dialogs.ask("🔄 " + i18n._("button.reboot_now") + " ?", i18n._("secureboot.reboot_confirm_message"),
                         on_yes=self.reboot, destructive=True)

    # ==================== Enrôlement MOK ====================

    def mok_enrollment_wizard(self):
        i18n = self.i18n
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=12, margin_bottom=18, margin_start=18, margin_end=18)

        box.append(markup_label(f"""<b>📋 {i18n._("secureboot.enrollment_instructions")}</b>

{i18n._("secureboot.enrollment_explanation")}

<b>1️⃣</b> {i18n._("secureboot.create_temp_password")}
   ⚠️ <i>{i18n._("secureboot.note_password")}</i>

<b>2️⃣</b> {i18n._("secureboot.system_will_reboot")}

<b>3️⃣</b> {i18n._("secureboot.mok_manager_screen")}
   • {i18n._("secureboot.select_enroll_mok")}
   • {i18n._("secureboot.select_continue")}
   • {i18n._("secureboot.select_yes")}
   • {i18n._("secureboot.enter_password")}
   • {i18n._("secureboot.select_reboot")}

<b>4️⃣</b> {i18n._("secureboot.key_enrolled_success")}"""))

        password = entry(placeholder="8-16 " + i18n._("secureboot.characters"), password=True)
        confirm = entry(password=True)
        box.append(labeled(i18n._("secureboot.temp_password") + " :", password))
        box.append(labeled(i18n._("secureboot.confirm") + " :", confirm))
        error_label = markup_label()
        box.append(error_label)

        def on_import():
            pw = password.get_text()
            if pw != confirm.get_text():
                error_label.set_markup(f"<span color='red'>{esc(i18n._('secureboot.passwords_dont_match'))}</span>")
                return False
            if not 8 <= len(pw) <= 16:
                error_label.set_markup(f"<span color='red'>{esc(i18n._('secureboot.password_length_error'))}</span>")
                return False

            ok_button.set_sensitive(False)
            error_label.set_markup(f"<i>{i18n._('secureboot.importing')}…</i>")

            def done(result):
                dialog.close()
                if result['success']:
                    self.sb.clear_mok_cache()
                    self.show_reboot_instructions()
                    self.update_history()
                else:
                    self.dialogs.show_error(i18n._("message.error.title"), result['message'])

            # pkexec : thread (le mot de passe temporaire passe sur stdin du helper)
            run_task(lambda: self.sb.enroll_mok_key(pw), done)
            return False

        dialog, ok_button = self.dialogs.window("🔐 " + i18n._("secureboot.mok_enrollment"), box,
                                                "✅ " + i18n._("secureboot.import_mok_key"), on_import,
                                                width=620, height=640)
        password.grab_focus()

    def show_reboot_instructions(self):
        i18n = self.i18n
        message = (f"{i18n._('secureboot.reboot_required')}\n\n"
                   f"{i18n._('secureboot.follow_mok_manager_instructions')}\n\n"
                   f"{i18n._('secureboot.reboot_now_question')}")
        self.dialogs.ask("✅ " + i18n._("secureboot.mok_key_imported"), message, on_yes=self.reboot,
                         yes_label="🔄 " + i18n._("button.reboot_now"), no_label="⏸️ " + i18n._("button.later"))

    # ==================== Signature des kernels ====================

    def module_signing_wizard(self):
        run_task(self.sb.get_custom_kernels, self._show_signing_dialog)

    def _show_signing_dialog(self, custom_kernels):
        i18n = self.i18n
        if not custom_kernels:
            self.dialogs.show_warning(i18n._("secureboot.module_signing"), i18n._("secureboot.no_custom_kernels"))
            return

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      margin_top=12, margin_bottom=18, margin_start=18, margin_end=18)
        box.append(markup_label(f"<big><b>✍️ {i18n._('secureboot.resign_custom_kernels')}</b></big>"))
        box.append(markup_label(f"<b>{len(custom_kernels)} {i18n._('secureboot.custom_kernels_detected')} :</b>"))

        checks = []
        kernel_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for kernel in custom_kernels:
            check = Gtk.CheckButton(active=True, label=(
                f"{kernel['kernel_version']} ({kernel['module_count']} {i18n._('secureboot.modules')})"))
            checks.append((check, kernel['kernel_version']))
            kernel_list.append(check)
        box.append(kernel_list)

        vmlinuz_check = Gtk.CheckButton(label="✅ " + i18n._("secureboot.also_sign_vmlinuz"), active=True)
        box.append(vmlinuz_check)

        status_label = markup_label()
        progress = Gtk.ProgressBar(show_text=True, visible=False)
        box.append(status_label)
        box.append(progress)

        def on_sign():
            selected = [version for check, version in checks if check.get_active()]
            if not selected:
                status_label.set_markup(f"<span color='red'>{esc(i18n._('secureboot.no_kernel_selected'))}</span>")
                return False

            sign_vmlinuz = vmlinuz_check.get_active()
            ok_button.set_sensitive(False)
            for check, _version in checks:
                check.set_sensitive(False)
            vmlinuz_check.set_sensitive(False)
            progress.set_visible(True)
            dialog.set_can_close(False)

            def work():
                totals = {"modules_signed": 0, "modules_failed": 0, "vmlinuz_signed": 0,
                          "vmlinuz_failed": 0, "errors": []}
                for task, kernel_ver in enumerate(selected):
                    def update(current, total, module_name, task=task, kernel_ver=kernel_ver):
                        fraction = (task + (current / total)) / len(selected) if total else 1.0
                        text = f"[{task + 1}/{len(selected)}] {kernel_ver} : {current}/{total}"
                        if module_name == "vmlinuz":
                            status = f"🔄 {i18n._('secureboot.signing_vmlinuz_for')} {kernel_ver}…"
                        elif module_name == "initrd":
                            status = f"🔄 {i18n._('secureboot.regenerating_initrd', version=kernel_ver)}"
                        elif module_name:
                            status = f"🔄 {i18n._('secureboot.signing_modules_for')} {kernel_ver}…\n📦 {module_name}"
                        else:
                            status = None
                        GLib.idle_add(lambda: (progress.set_fraction(fraction), progress.set_text(text),
                                               status and status_label.set_text(status), False)[-1])

                    logging.info(f"Signature de {kernel_ver} (vmlinuz={sign_vmlinuz})")
                    result = self.sb.sign_kernel_complete(kernel_ver, sign_vmlinuz_flag=sign_vmlinuz,
                                                          progress_callback=update)
                    logging.info(f"Résultat {kernel_ver} : {result}")

                    totals["modules_signed"] += result['modules_signed']
                    totals["modules_failed"] += result['modules_failed']
                    if result['vmlinuz_signed']:
                        totals["vmlinuz_signed"] += 1
                    elif sign_vmlinuz:
                        totals["vmlinuz_failed"] += 1
                    if not result['success']:
                        totals["errors"].append(f"{kernel_ver} : {result['message']}")
                return totals

            def done(totals):
                dialog.force_close()
                self.show_signing_results(totals)
                self.update_history()

            def failed(error):
                dialog.force_close()
                self.dialogs.show_error(i18n._("message.error.title"), str(error))

            run_task(work, done, failed)
            return False

        dialog, ok_button = self.dialogs.window("✍️ " + i18n._("secureboot.module_signing"), box,
                                                "✍️ " + i18n._("secureboot.sign_modules"), on_sign,
                                                width=680, height=560)

    def show_signing_results(self, totals):
        i18n = self.i18n
        text = (f"{i18n._('secureboot.modules_signed')}: {totals['modules_signed']}\n"
                f"{i18n._('secureboot.modules_failed')}: {totals['modules_failed']}\n"
                f"{i18n._('secureboot.vmlinuz_signed')}: {totals['vmlinuz_signed']}\n"
                f"{i18n._('secureboot.vmlinuz_failed')}: {totals['vmlinuz_failed']}\n\n")
        if totals['modules_failed'] == 0 and totals['vmlinuz_failed'] == 0 and not totals['errors']:
            text += "✅ " + i18n._("secureboot.all_signed_successfully")
            text += "\n\n" + i18n._("secureboot.next_steps_update_grub")
        else:
            text += "⚠️ " + i18n._("secureboot.some_signing_failed")
            if totals['errors']:
                text += "\n\n" + "\n".join(totals['errors'])
        self.dialogs.show_info("📊 " + i18n._("secureboot.signing_results"), text)

    # ==================== Statut ====================

    def _build_status(self):
        i18n = self.i18n
        box = page_box()

        status, inner = section(i18n._("secureboot.current_status"))
        self.status_label = markup_label()
        inner.append(self.status_label)
        inner.append(button_row(button(i18n._("button.refresh"), self.update_status)))
        box.append(status)

        deps, inner = section(i18n._("secureboot.dependencies"))
        self.deps_label = markup_label()
        inner.append(self.deps_label)
        inner.append(button_row(button(i18n._("secureboot.install_dependencies"), self.install_dependencies)))
        box.append(deps)

        info, inner = section(i18n._("secureboot.instructions"))
        label = markup_label()
        label.set_text(i18n._("secureboot.instructions_text"))
        inner.append(label)
        box.append(info)

        self.update_status()
        self.update_dependencies()
        return Gtk.ScrolledWindow(child=box, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)

    def update_status(self):
        i18n = self.i18n
        info = self.sb.get_system_info()
        lines = []
        if not info['is_uefi']:
            lines.append(f"❌ <b>{i18n._('secureboot.uefi_mode')}:</b> {i18n._('secureboot.disabled')} - "
                         f"{i18n._('secureboot.legacy_boot')}")
            self.status_label.set_markup('\n'.join(lines))
            return

        lines.append(f"✅ <b>{i18n._('secureboot.uefi_mode')}:</b> {i18n._('secureboot.enabled')}")
        sb_status = info['secureboot_status']
        if sb_status['enabled']:
            lines.append(f"🛡️ <b>SecureBoot:</b> <span color='green'>{i18n._('secureboot.enabled')}</span>")
        else:
            lines.append(f"🔓 <b>SecureBoot:</b> <span color='orange'>{i18n._('secureboot.disabled')}</span>")
        lines.append(f"   <i>{esc(sb_status['details'])}</i>")
        if info['setup_mode']:
            lines.append(f"⚙️ <b>{i18n._('secureboot.setup_mode')}:</b> "
                         f"<span color='orange'>{i18n._('secureboot.active')}</span>")
        self.status_label.set_markup('\n'.join(lines))

    def update_dependencies(self):
        i18n = self.i18n
        lines = []
        for name, installed in self.sb.check_dependencies()['dependencies'].items():
            if installed:
                lines.append(f"✅ <b>{name}:</b> {i18n._('secureboot.installed')}")
            else:
                lines.append(f"❌ <b>{name}:</b> <span color='red'>{i18n._('secureboot.not_installed')}</span>")
        self.deps_label.set_markup('\n'.join(lines))

    def install_dependencies(self):
        i18n = self.i18n
        deps = self.sb.check_dependencies()
        if deps['all_installed']:
            self.dialogs.show_info(i18n._("message.info.title"), i18n._("secureboot.all_dependencies_installed"))
            return

        def work():
            missing = deps['dependencies']
            packages = []
            if not missing['mokutil']:
                packages.append(('mokutil', i18n._('secureboot.dep.mokutil')))
            if not missing['openssl']:
                packages.append(('openssl', i18n._('secureboot.dep.openssl')))
            if not missing['sbsign'] or not missing['sbverify']:
                packages.append(('sbsigntool', i18n._('secureboot.dep.sbsigntool')))
            if not missing['sign-file']:
                kbuild = find_available_kbuild_package()  # apt-cache : thread
                packages.append((kbuild, i18n._('secureboot.dep.sign_file')))
            if not missing['modinfo']:
                packages.append(('kmod', i18n._('secureboot.dep.kmod')))
            return packages

        def confirm(packages):
            if not packages:
                self.dialogs.show_info(i18n._("message.info.title"), i18n._("secureboot.all_dependencies_installed"))
                return
            names = [name for name, _ in packages]
            details = f"{i18n._('secureboot.packages')}:\n" + "\n".join(f"  • {n} ({d})" for n, d in packages)
            self.dialogs.ask(i18n._("secureboot.install_dependencies_confirm"), details,
                             on_yes=lambda: self._apt_install(names))

        run_task(work, confirm)

    def _apt_install(self, names):
        i18n = self.i18n
        progress = self.dialogs.progress(i18n._("secureboot.install_dependencies"), ", ".join(names))
        progress.pulse()

        def done(result):
            progress.close()
            success, _, error = result
            self.update_dependencies()
            if success:
                self.dialogs.toast(i18n._("message.success.operation"))
            else:
                self.dialogs.show_error(i18n._("message.error.title"), error or i18n._("message.error.operation"))

        def failed(error):
            progress.close()
            self.dialogs.show_error(i18n._("message.error.title"), str(error))

        run_task(lambda: PkexecHelper.apt_install(*names), done, failed)

    # ==================== Clés MOK ====================

    def _build_keys(self):
        i18n = self.i18n
        box = page_box()

        enrolled, inner = section(i18n._("secureboot.enrolled_keys"))
        enrolled.set_vexpand(True)
        scrolled, self.enrolled_view = monospace_view()
        scrolled.set_min_content_height(160)
        inner.append(scrolled)
        inner.append(button_row(button(i18n._("button.refresh"), lambda: self.update_enrolled_keys(True))))
        box.append(enrolled)

        manage, inner = section(i18n._("secureboot.manage_keys"))
        import_entry = entry(placeholder=i18n._("secureboot.key_file_path"))
        row = labeled(i18n._("secureboot.import_key") + " :", import_entry)
        row.append(button("📁", lambda: self.browse(import_entry, "secureboot.select_key_file",
                                                    i18n._("secureboot.key_files"), KEY_FILTERS_PATTERNS)))
        row.append(button(i18n._("secureboot.import"), lambda: self.import_mok_key(import_entry)))
        inner.append(row)
        inner.append(button_row(button(i18n._("secureboot.reset_keys"), self.reset_mok_keys,
                                       "destructive-action")))
        inner.append(markup_label(f"<span color='orange'>⚠️ {i18n._('secureboot.keys_warning')}</span>"))
        box.append(manage)
        return box

    def update_enrolled_keys(self, clear_cache=False):
        i18n = self.i18n
        buffer = self.enrolled_view.get_buffer()
        buffer.set_text(i18n._("secureboot.analyzing") + "…")

        def work():
            if clear_cache:
                self.sb.clear_mok_cache()
            return self.sb.list_enrolled_keys()

        def done(result):
            if result['success']:
                if result['keys']:
                    text = f"{i18n._('secureboot.enrolled_keys_count')}: {len(result['keys'])}\n\n"
                    text += result['raw_output']
                else:
                    text = i18n._("secureboot.no_enrolled_keys")
            else:
                text = f"{i18n._('message.error.title')}: {result.get('error', 'Unknown error')}"
            buffer.set_text(text)

        run_task(work, done)

    def browse(self, target_entry, title_key, filter_name, patterns):
        i18n = self.i18n
        filters = [(filter_name, patterns), (i18n._("secureboot.all_files"), ["*"])]
        self.dialogs.open_file(i18n._(title_key), target_entry.set_text, filters,
                               initial_folder=self.sb.keys_dir if self.sb.keys_dir.is_dir() else None)

    def import_mok_key(self, import_entry):
        i18n = self.i18n
        key_file = import_entry.get_text().strip()
        if not key_file:
            self.dialogs.show_error(i18n._("message.error.title"), i18n._("secureboot.no_key_file"))
            return
        # mokutil demande un mot de passe temporaire : import dans un terminal
        self.dialogs.ask(i18n._("secureboot.import_key_confirm"), i18n._("secureboot.import_key_details"),
                         on_yes=lambda: self.run_in_terminal(PkexecHelper.terminal_command("mokutil-import", key_file)))

    def reset_mok_keys(self):
        i18n = self.i18n
        self.dialogs.ask(i18n._("secureboot.reset_keys_confirm"), i18n._("secureboot.reset_keys_warning"),
                         destructive=True,
                         on_yes=lambda: self.run_in_terminal(PkexecHelper.terminal_command("mokutil-reset")))

    def run_in_terminal(self, command):
        if launch_in_terminal(command) is None:
            self.dialogs.show_error(self.i18n._("message.error.title"), self.i18n._("secureboot.no_terminal"))

    # ==================== Signature manuelle ====================

    def _build_signing(self):
        i18n = self.i18n
        box = page_box()

        generate, inner = section(i18n._("secureboot.generate_key"))
        key_name = entry(text="MOK", placeholder="MOK")
        common_name = entry(placeholder="Kernel Module Signing Key")
        inner.append(labeled(i18n._("secureboot.key_name") + " :", key_name))
        inner.append(labeled(i18n._("secureboot.common_name") + " :", common_name))
        result_label = markup_label(selectable=True)
        inner.append(button_row(button(i18n._("secureboot.generate"),
                                       lambda: self.generate_key(key_name, common_name, result_label),
                                       "suggested-action")))
        inner.append(result_label)
        box.append(generate)

        sign, inner = section(i18n._("secureboot.sign_module"))
        module_entry = entry(placeholder="/path/to/module.ko")
        priv_entry = entry(placeholder="/path/to/key.priv")
        cert_entry = entry(placeholder="/path/to/cert.der")
        for label_key, field, title_key, filter_name, patterns in (
                ("secureboot.module_file", module_entry, "secureboot.select_module_file",
                 i18n._("secureboot.kernel_modules"), ["*.ko"]),
                ("secureboot.private_key", priv_entry, "secureboot.select_key_file",
                 i18n._("secureboot.key_files"), KEY_FILTERS_PATTERNS),
                ("secureboot.certificate", cert_entry, "secureboot.select_key_file",
                 i18n._("secureboot.key_files"), KEY_FILTERS_PATTERNS)):
            row = labeled(i18n._(label_key) + " :", field)
            row.append(button("📁", lambda f=field, t=title_key, n=filter_name, p=patterns: self.browse(f, t, n, p)))
            inner.append(row)
        sign_result = markup_label(selectable=True)
        inner.append(button_row(button(i18n._("secureboot.sign"),
                                       lambda: self.sign_module(module_entry, priv_entry, cert_entry, sign_result),
                                       "suggested-action")))
        inner.append(sign_result)
        box.append(sign)

        return Gtk.ScrolledWindow(child=box, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)

    def generate_key(self, name_entry, cn_entry, result_label):
        i18n = self.i18n
        key_name = name_entry.get_text().strip() or "MOK"
        common_name = cn_entry.get_text().strip() or None

        def done(result):
            if result['success']:
                result_label.set_markup(
                    f"✅ {i18n._('secureboot.key_generated')}\n\n"
                    f"🔑 {i18n._('secureboot.private_key')}: {esc(str(result['priv_key']))}\n"
                    f"📜 {i18n._('secureboot.certificate')}: {esc(str(result['der_cert']))}\n"
                    f"📄 PEM: {esc(str(result['pem_cert']))}")
                self.update_history()
            else:
                result_label.set_markup(f"❌ {i18n._('message.error.title')}: {esc(str(result['error']))}")

        run_task(lambda: self.sb.generate_signing_key(key_name, common_name), done)

    def sign_module(self, module_entry, priv_entry, cert_entry, result_label):
        i18n = self.i18n
        paths = [e.get_text().strip() for e in (module_entry, priv_entry, cert_entry)]
        if not all(paths):
            result_label.set_markup(f"❌ {i18n._('secureboot.fill_all_fields')}")
            return

        def done(result):
            if result['success']:
                result_label.set_markup(f"✅ {esc(result['message'])}")
                self.update_history()
            else:
                result_label.set_markup(f"❌ {i18n._('message.error.title')}: {esc(str(result['error']))}")

        run_task(lambda: self.sb.sign_kernel_module(*paths), done)

    # ==================== Historique ====================

    def _build_history(self):
        i18n = self.i18n
        box = page_box()
        box.append(button_row(
            button(i18n._("button.refresh"), self.update_history),
            button(i18n._("button.clear"), self.clear_history, "destructive-action"),
        ))
        scrolled, self.history_view = monospace_view()
        box.append(scrolled)
        return box

    def update_history(self):
        i18n = self.i18n
        history = self.sb.get_history()
        buffer = self.history_view.get_buffer()
        if not history:
            buffer.set_text(i18n._("secureboot.no_history"))
            return

        text = f"{i18n._('secureboot.history_count')}: {len(history)}\n\n"
        for item in history:
            timestamp = datetime.fromisoformat(item['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
            text += f"{'✅' if item['success'] else '❌'} [{timestamp}] {item['action']}\n"
            if isinstance(item['details'], dict):
                for key, value in item['details'].items():
                    text += f"   {key}: {value}\n"
            else:
                text += f"   {item['details']}\n"
            text += "\n"
        buffer.set_text(text)

    def clear_history(self):
        def do_clear():
            self.sb._save_history([])
            self.update_history()
        self.dialogs.ask(self.i18n._("message.confirm.title"), self.i18n._("secureboot.clear_history_confirm"),
                         on_yes=do_clear, destructive=True)


def find_available_kbuild_package():
    """Paquet linux-kbuild (contient sign-file) disponible pour le kernel en cours"""
    kernel_version = os.uname().release
    match = re.match(r'(\d+\.\d+)(\.\d+)?', kernel_version)
    if not match:
        return f'linux-headers-{kernel_version}'

    major_minor = match.group(1)
    candidates = [f'linux-kbuild-{match.group(0)}', f'linux-kbuild-{major_minor}']
    try:
        result = subprocess.run(['apt-cache', 'search', '--names-only', f'^linux-kbuild-{major_minor}'],
                                capture_output=True, text=True, check=False)
        available = sorted(m.group(1) for line in result.stdout.splitlines()
                           if (m := re.match(r'^(linux-kbuild-[\d.+a-z]+)', line)))
        for candidate in candidates:
            if candidate in available:
                return candidate
        if available:
            return available[-1]
    except OSError as e:
        logging.debug(f"Recherche de linux-kbuild : {e}")

    # Repli : les headers du kernel en cours contiennent aussi scripts/sign-file
    return f'linux-headers-{kernel_version}'


def create_secureboot_tab(main_window):
    """Crée l'onglet de gestion SecureBoot"""
    page = SecureBootPage(main_window)
    main_window.secureboot_page = page
    return page.build()
