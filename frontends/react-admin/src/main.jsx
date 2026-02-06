import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || `${window.location.origin}/api`
).replace(/\/$/, "");
const TOKEN_STORAGE_KEY = "admin_access_token";
const UI_LANGUAGE_STORAGE_KEY = "admin_ui_language";

const COLORS = {
  background: "#f8fafc",
  card: "#ffffff",
  border: "#cbd5f5",
  primary: "#2563eb",
  primaryDark: "#1d4ed8",
  text: "#0f172a",
  secondaryText: "#475569",
  danger: "#dc2626",
  success: "#166534",
};

const LAYOUT = {
  container: {
    minHeight: "100vh",
    backgroundColor: COLORS.background,
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif",
    padding: "2rem",
    boxSizing: "border-box",
  },
  card: {
    maxWidth: "1180px",
    margin: "0 auto",
    backgroundColor: COLORS.card,
    borderRadius: "18px",
    boxShadow: "0 40px 80px -28px rgba(15, 23, 42, 0.25)",
    padding: "2.5rem",
  },
};

const buttonStyle = (variant = "primary") => {
  const base = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "10px",
    padding: "0.65rem 1.25rem",
    fontWeight: 600,
    fontSize: "0.95rem",
    border: "none",
    cursor: "pointer",
    transition: "transform 0.15s ease, box-shadow 0.15s ease",
  };

  if (variant === "primary") {
    return {
      ...base,
      color: "#ffffff",
      background: `linear-gradient(135deg, ${COLORS.primary} 0%, ${COLORS.primaryDark} 100%)`,
      boxShadow: "0 10px 25px -12px rgba(37, 99, 235, 0.6)",
    };
  }

  if (variant === "ghost") {
    return {
      ...base,
      backgroundColor: "transparent",
      color: COLORS.secondaryText,
      border: `1px solid ${COLORS.border}`,
    };
  }

  if (variant === "danger") {
    return {
      ...base,
      color: "#ffffff",
      backgroundColor: COLORS.danger,
      boxShadow: "0 10px 25px -12px rgba(220, 38, 38, 0.4)",
    };
  }

  return {
    ...base,
    backgroundColor: "#e2e8f0",
    color: COLORS.secondaryText,
  };
};

const formatDateTime = (value, language) => {
  if (!value) {
    return "";
  }
  try {
    return new Intl.DateTimeFormat(language || "en", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch (err) {
    return new Date(value).toLocaleString();
  }
};

const toLocalInputValue = (value) => {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const offsetMs = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
};

const toIsoDateTime = (value) => {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toISOString();
};

const formatBytes = (bytes) => {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / Math.pow(1024, exponent);
  const formatted =
    value >= 10 || exponent === 0 ? value.toFixed(0) : value.toFixed(1);
  return `${formatted} ${units[exponent]}`;
};

const resolveLabel = (t, keyPrefix, value) => {
  if (!value) return t("common.notAvailable");
  const key = `${keyPrefix}.${value}`;
  const label = t(key);
  return label === key ? value : label;
};

const resolveCourtStatusLabel = (t, value) =>
  resolveLabel(t, "courts.status", value);

const resolveCourtCategoryLabel = (t, value) =>
  resolveLabel(t, "courts.category", value);

const resolveContractStatusLabel = (t, value) =>
  resolveLabel(t, "contracts.status", value);

const resolveTaskStatusLabel = (t, value) =>
  resolveLabel(t, "tasks.statuses", value);

const resolveTaskKindLabel = (t, value) =>
  resolveLabel(t, "tasks.kinds", value);

const resolveGoodDeedStatusLabel = (t, value) =>
  resolveLabel(t, "goodDeeds.statuses", value);

const resolveGoodDeedCategoryLabel = (t, value) =>
  resolveLabel(t, "goodDeeds.categories", value);

const resolveGoodDeedHelpTypeLabel = (t, value) =>
  resolveLabel(t, "goodDeeds.helpTypes", value);

const resolveShariahStatusLabel = (t, value) =>
  resolveLabel(t, "shariah.statuses", value);

const resolveShariahAreaLabel = (t, value) =>
  resolveLabel(t, "shariah.areas", value);

const resolveRoleLabel = (t, slug) => {
  const key = `roles.labels.${slug}`;
  const label = t(key);
  return label === key ? slug : label;
};

const SUPPORTED_UI_LANGUAGES = ["ru", "en"];

const UI_TRANSLATIONS = {
  en: {
    languageNames: { ru: "Russian", en: "English" },
    common: {
      yes: "Yes",
      no: "No",
      notAvailable: "-",
      loading: "Loading:",
      save: "Save",
      cancel: "Cancel",
      delete: "Delete",
      add: "Add",
      reset: "Reset",
      upload: "Upload",
      download: "Download",
      replace: "Replace",
      view: "View",
      actions: "Actions",
    },
    errors: {
      requestFailed: "Request failed ({{status}}).",
      sessionExpired: "Session expired. Please sign in again.",
      forbidden: "You do not have permission to view this section.",
    },
    actions: { logout: "Log out" },
    login: {
      title: "Admin Panel",
      subtitle: "Enter your credentials to continue.",
      usernameLabel: "Username",
      passwordLabel: "Password",
      usernamePlaceholder: "admin",
      passwordPlaceholder: "********",
      submit: "Sign in",
      submitting: "Signing in:",
      error: "Unable to sign in. Please try again.",
      otpTitle: "Enter OTP",
      otpSubtitle: "We sent a code to your Telegram @{{username}}",
      otpLabel: "One-time code",
      otpPlaceholder: "123456",
      otpSubmit: "Verify code",
    },
    dashboard: {
      welcome: "Welcome, {{username}}",
      subtitle: "Manage users, languages, links, and documents from a single place.",
    },
    tabs: {
      userManagement: "User management",
      users: "Users",
      roles: "Roles",
      languages: "Languages",
      links: "Links",
      blacklist: "Blacklist",
      tasks: "Tasks",
      courts: "Courts",
      contracts: "Contracts",
      documents: "Documents",
      templates: "Templates",
      shariahControl: "Shariah control",
    },
    tasks: {
      title: "Work items",
      allTopics: "All topics",
      empty: "No tasks found.",
      errorLoad: "Failed to load tasks.",
      open: "Open",
      take: "Take",
      refresh: "Refresh",
      topic: "Topic",
      status: "Status",
      mine: "Mine",
      unassigned: "Unassigned",
      details: "Details",
      events: "Events",
      comment: "Comment",
      addComment: "Add comment",
      notify: "Message user",
      send: "Send",
      updateStatus: "Update status",
      viewSpec: "View spec",
      close: "Close",
      id: "ID",
      kind: "Type",
      priority: "Priority",
      targetUser: "Target user",
      created: "Created",
      statuses: {
        new: "New",
        assigned: "Assigned",
        in_progress: "In progress",
        waiting_user: "Waiting for user",
        waiting_scholar: "Waiting for scholar",
        done: "Done",
        canceled: "Cancelled",
      },
      kinds: {
        case_created: "Case created",
        needs_review: "Needs review",
        scholar_request: "Scholar request",
        moderation_incident: "Moderation incident",
      },
    },
    courts: {
      admin: {
        title: "Court case",
        caseNumber: "Case",
        status: "Status",
        statusValue: "Status",
        scholarName: "Scholar name",
        scholarContact: "Scholar contact",
        scholarId: "Scholar ID",
        update: "Update case",
        statusUpdate: "Change",
        assignee: "Responsible",
        category: "Category",
        plaintiff: "Plaintiff",
        defendant: "Defendant",
        created: "Created",
        evidence: "Evidence",
        scholarSelect: "Select scholar",
        scholarSelectPlaceholder: "Choose from list",
        scholarEmpty: "No scholars available",
        assignTitle: "Assign responsible",
        assignSelf: "You can assign only yourself.",
        assignAction: "Assign",
      },
      status: {
        open: "Open",
        in_progress: "In progress",
        closed: "Closed",
        cancelled: "Cancelled",
      },
      category: {
        financial: "Financial dispute",
        contract_breach: "Contract breach",
        property: "Property / rent",
        goods: "Goods / supply",
        services: "Services / work",
        family: "Family matter",
        ethics: "Ethical conflict",
        unknown: "Unknown category",
      },
    },
    contracts: {
      admin: {
        title: "Contract",
        status: "Status",
        statusValue: "Status",
        assignee: "Responsible",
        created: "Created",
        contractType: "Type",
        contractTitle: "Title",
        owner: "Owner",
        counterparty: "Counterparty",
        scholarName: "Scholar name",
        scholarContact: "Scholar contact",
        scholarId: "Scholar ID",
        update: "Update contract",
        statusUpdate: "Change",
        scholarSelect: "Select scholar",
        scholarSelectPlaceholder: "Choose from list",
        scholarEmpty: "No scholars available",
        assignTitle: "Assign responsible",
        assignSelf: "You can assign only yourself.",
        assignAction: "Assign",
        delete: "Delete contract",
        deleteConfirm: "Delete this contract? This action cannot be undone.",
        text: "Contract text",
      },
      status: {
        draft: "Draft",
        confirmed: "Confirmed",
        sent_to_party: "Sent to party",
        party_approved: "Approved by party",
        party_changes_requested: "Changes requested",
        signed: "Signed",
        sent_to_scholar: "Sent to scholar",
        scholar_send_failed: "Scholar send failed",
        sent: "Sent",
      },
    },
    roles: {
      title: "Roles & permissions",
      loading: "Loading roles:",
      error: "Failed to load roles or admin accounts.",
      rolesTitle: "Available roles",
      accountsTitle: "Admin accounts",
      username: "Username",
      password: "Password",
      rolePick: "Initial role (optional)",
      rolePlaceholder: "No role on creation",
      telegram: "Telegram",
      create: "Create account",
      creating: "Creating...",
      created: "Account created",
      createError: "Please fill username and password.",
      assign: "Assign",
      revoke: "Revoke",
      emptyRoles: "No roles yet.",
      emptyAccounts: "No admin accounts yet.",
      account: "Account",
      status: "Status",
      roleList: "Roles",
      actions: "Actions",
      notAllowed: "You don't have permission to manage roles.",
      ownerOnly: "Only owner can manage this role.",
      labels: {
        admin_blacklist: "Blacklist admin",
        admin_documents: "Documents admin",
        admin_languages: "Languages admin",
        admin_links: "Links admin",
        admin_templates: "Templates admin",
        admin_work_items_view: "Tasks viewer",
        admin_work_items_manage: "Tasks manager",
        admin_users: "Users admin",
        tz_nikah: "TZ: Nikah",
        tz_inheritance: "TZ: Inheritance",
        tz_spouse_search: "TZ: Spouse search",
        tz_courts: "TZ: Courts",
        tz_contracts: "TZ: Contracts",
        tz_good_deeds: "TZ: Good deeds",
        tz_execution: "TZ: Execution",
        shariah_chief: "Shariah chief",
        shariah_observer: "Shariah observer",
        owner: "Owner",
        superadmin: "Super admin",
        scholar: "Scholar",
      },
    },
    users: {
      loading: "Loading users:",
      error: "Failed to load users.",
      empty: "No users yet.",
      columns: {
        status: "Status",
        fullName: "Name",
        telegramId: "Telegram ID",
        phone: "Phone",
        created: "Created",
        language: "Language",
        role: "Role",
        alive: "Alive",
        banned: "Banned",
      },
      role: { user: "User" },
      actions: {
        ban: "Ban",
        unban: "Unban",
        viewRequest: "View request",
        approveUnban: "Unban",
        close: "Close",
        attention: "Attention",
        makeAdmin: "Make admin",
        delete: "Delete",
      },
      adminForm: {
        username: "Admin login",
        password: "Password",
        role: "Role",
        create: "Create admin",
        creating: "Creating...",
        success: "Admin created",
        error: "Failed to create admin. Check fields.",
        update: "Save changes",
        updateSuccess: "Admin updated",
        updateError: "Failed to update admin.",
        updateHint: "Update password or role.",
      },
    },
    blacklist: {
      title: "Blacklist",
      description: "Manage blacklist entries and review associated complaints and appeals.",
      loading: "Loading blacklist:",
      empty: "No blacklist entries yet.",
      errorLoad: "Failed to load blacklist.",
      errorLoadDetail: "Failed to load entry details.",
      columns: {
        name: "Name",
        phone: "Phone",
        city: "City",
        birthdate: "Birthdate",
        isActive: "Status",
        complaints: "Complaints",
        appeals: "Appeals",
        added: "Added",
        actions: "Actions",
      },
      status: {
        active: "Active",
        inactive: "Inactive",
      },
      actions: {
        refresh: "Refresh",
        activate: "Activate",
        deactivate: "Deactivate",
      },
      modal: {
        title: "Blacklist entry: {{name}}",
        status: "Status",
        city: "City",
        phone: "Phone",
        birthdate: "Birthdate",
        complaintsTitle: "Complaints",
        complaintsEmpty: "No complaints yet.",
        complaintHeader: "{{date}} — {{author}}",
        appealsTitle: "Appeals",
        appealsEmpty: "No appeals yet.",
        appealHeader: "{{date}} — {{author}}",
        attachmentsTitle: "Attachments",
        attachmentsEmpty: "No attachments.",
        attachmentDownload: "Download",
        close: "Close",
      },
    },
    languages: {
      title: "Languages",
      loading: "Loading languages:",
      selectPrompt: "Select a language to edit translations.",
      listDefaultMark: "default",
      deleteButton: "Delete",
      deleteConfirm: "Delete language {{code}}?",
      addLabel: "Add language code",
      addPlaceholder: "e.g. en",
      addButton: "Add",
      translationsTitle: "Translations ({{code}})",
      translationsLoading: "Loading translations:",
      translationIdentifier: "Key",
      translationValue: "Value",
      translationEmpty: "No translations yet.",
      translationAI: "AI translate",
      translationSave: "Save",
      errorLoad: "Failed to load languages.",
      errorTranslations: "Failed to load translations.",
      errorAdd: "Failed to add language.",
      errorDelete: "Failed to delete language.",
      errorUpdate: "Failed to update translation.",
      infoAdded: "Language {{code}} added.",
      infoDeleted: "Language {{code}} deleted.",
      infoSaved: "Saved {{identifier}} for {{code}}.",
    },
    links: {
      languageLabel: "Language",
      description: "Set links for each slot in the selected language.",
      defaultHint: "Leave empty to use default.",
      placeholder: "https://example.com",
      save: "Save",
      reset: "Reset",
      successSave: "Saved.",
      successReset: "Reset to default.",
      errorLoad: "Failed to load link settings.",
      errorSave: "Failed to save link.",
      empty: "No link slots configured.",
      table: {
        slot: "Slot",
        url: "URL",
      },
    },
    documents: {
      treeTitle: "Topics",
      uploadTitle: "Upload document",
      selectLanguage: "Language",
      selectFile: "File",
      uploadButton: "Upload",
      noLanguages: "No languages available. Add a language first.",
      placeholder: "Select a topic on the left.",
      loading: "Loading documents:",
      empty: "No documents yet.",
      table: {
        filename: "File",
        language: "Lang",
        size: "Size",
        uploaded: "Uploaded",
      },
      actions: {
        view: "View",
        replace: "Replace",
        delete: "Delete",
      },
      deleteConfirm: "Delete {{name}}?",
      successUpload: "Uploaded.",
      errorUpload: "Failed to upload document.",
      successReplace: "Replaced.",
      errorReplace: "Failed to replace document.",
      successDelete: "Deleted.",
      errorDelete: "Failed to delete document.",
      errorLoad: "Failed to load data.",
    },
    contractTemplates: {
      treeTitle: "Categories",
      uploadTitle: "Upload template",
      selectLanguage: "Language",
      selectFile: "File",
      uploadButton: "Upload",
      noLanguages: "No languages available. Add a language first.",
      placeholder: "Select a template group on the left.",
      loading: "Loading templates:",
      empty: "No templates yet.",
      table: {
        filename: "File",
        language: "Lang",
        size: "Size",
        uploaded: "Uploaded",
      },
      actions: {
        view: "View",
        replace: "Replace",
        delete: "Delete",
      },
      deleteConfirm: "Delete {{name}}?",
      successUpload: "Uploaded.",
      errorUpload: "Failed to upload template.",
      successReplace: "Replaced.",
      errorReplace: "Failed to replace template.",
      successDelete: "Deleted.",
      errorDelete: "Failed to delete template.",
      errorLoad: "Failed to load data.",
    },
    shariahControl: {
      tabs: {
        deeds: "Good deeds",
        needy: "Needy requests",
        confirmations: "Confirmations",
        applications: "Admin applications",
      },
      empty: "No available sections for your role.",
    },
    goodDeeds: {
      title: "Good deeds",
      listEmpty: "No good deeds found.",
      needyEmpty: "No needy requests found.",
      confirmationsEmpty: "No confirmations found.",
      filters: {
        status: "Status",
        city: "City",
        country: "Country",
        deedId: "Good deed ID",
      },
      columns: {
        id: "ID",
        title: "Title",
        person: "Type",
        user: "User",
        city: "City",
        country: "Country",
        status: "Status",
        created: "Created",
        goodDeed: "Good deed",
      },
      detail: {
        title: "Good deed",
        needyTitle: "Needy request",
        confirmationTitle: "Confirmation",
        user: "User",
        phone: "Phone",
        email: "Email",
        description: "Description",
        helpType: "Help type",
        amount: "Amount",
        comment: "Comment",
        status: "Status",
        approvedCategory: "Approved category",
        reviewComment: "Review comment",
        clarificationText: "Clarification",
        clarificationAttachment: "Clarification attachment",
        created: "Created",
        updated: "Updated",
        approvedAt: "Approved at",
        completedAt: "Completed at",
        reason: "Reason",
        allowZakat: "Zakat allowed",
        allowFitr: "Fitr allowed",
        sadaqaOnly: "Sadaqa only",
        text: "Text",
        attachment: "Attachment",
        goodDeed: "Good deed",
      },
      decision: {
        title: "Decision",
        status: "Decision",
        comment: "Comment",
        category: "Approved category",
        submit: "Save decision",
      },
      historyTitle: "History",
      downloadClarification: "Download clarification",
      downloadAttachment: "Download attachment",
      statuses: {
        pending: "Pending",
        needs_clarification: "Needs clarification",
        approved: "Approved",
        in_progress: "In progress",
        completed: "Completed",
        rejected: "Rejected",
      },
      decisionStatuses: {
        approved: "Approve",
        needs_clarification: "Request clarification",
        rejected: "Reject",
      },
      categories: {
        zakat: "Allowed for zakat",
        fitr: "Allowed for fitr",
        sadaqa: "Sadaqa only",
      },
      helpTypes: {
        zakat: "Zakat",
        fitr: "Fitr",
        sadaqa: "Sadaqa",
        general: "General help",
      },
    },
    shariah: {
      title: "Shariah applications",
      listEmpty: "No applications found.",
      filters: {
        status: "Status",
      },
      columns: {
        id: "ID",
        fullName: "Full name",
        status: "Status",
        country: "Country",
        city: "City",
        created: "Created",
      },
      detail: {
        title: "Application",
        fullName: "Full name",
        country: "Country",
        city: "City",
        educationPlace: "Education",
        educationCompleted: "Completed",
        educationDetails: "Education details",
        knowledgeAreas: "Knowledge areas",
        experience: "Experience",
        responsibility: "Responsibility accepted",
        status: "Status",
        meeting: "Meeting",
        meetingType: "Type",
        meetingLink: "Link",
        meetingAt: "Date/time",
        decisionComment: "Decision comment",
        assignedRoles: "Assigned roles",
        user: "User",
        phone: "Phone",
        email: "Email",
        created: "Created",
        updated: "Updated",
      },
      schedule: {
        title: "Schedule meeting",
        type: "Meeting type",
        link: "Meeting link",
        date: "Date and time",
        submit: "Schedule",
      },
      decision: {
        title: "Decision",
        status: "Decision",
        comment: "Comment",
        roles: "Roles (1-2)",
        roleHint: "Select up to 2 roles.",
        submit: "Save decision",
      },
      historyTitle: "History",
      statuses: {
        pending_intro: "Waiting for intro",
        meeting_scheduled: "Meeting scheduled",
        approved: "Approved",
        observer: "Observer",
        rejected: "Rejected",
      },
      meetingTypes: {
        video: "Video call",
        audio: "Audio call",
      },
      areas: {
        fiqh: "Fiqh",
        contracts: "Contracts",
        courts: "Court matters",
        zakat: "Zakat / Sadaqa",
        execution: "Execution",
        observer: "Observer",
      },
    },
  },
  ru: {
    languageNames: { ru: "Русский", en: "Английский" },
    common: {
      yes: "Да",
      no: "Нет",
      notAvailable: "-",
      loading: "Загрузка:",
      save: "Сохранить",
      cancel: "Отмена",
      delete: "Удалить",
      add: "Добавить",
      reset: "Сбросить",
      upload: "Загрузить",
      download: "Скачать",
      replace: "Заменить",
      view: "Посмотреть",
      actions: "Действия",
    },
    errors: {
      requestFailed: "Не удалось выполнить запрос ({{status}}).",
      sessionExpired: "Сессия истекла. Войдите заново.",
      forbidden: "Недостаточно прав для просмотра.",
    },
    actions: { logout: "Выйти" },
    login: {
      title: "Админ-панель",
      subtitle: "Введите логин и пароль, чтобы продолжить.",
      usernameLabel: "Логин",
      passwordLabel: "Пароль",
      usernamePlaceholder: "admin",
      passwordPlaceholder: "********",
      submit: "Войти",
      submitting: "Входим:",
      error: "Не удалось войти. Попробуйте ещё раз.",
      otpTitle: "Введите код",
      otpSubtitle: "Мы отправили код в Telegram @{{username}}",
      otpLabel: "Одноразовый код",
      otpPlaceholder: "123456",
      otpSubmit: "Подтвердить",
    },
    dashboard: {
      welcome: "Добро пожаловать, {{username}}",
      subtitle: "Управляйте пользователями, языками, ссылками и документами в одном месте.",
    },
    tabs: {
      userManagement: "Управление пользователями",
      users: "Пользователи",
      roles: "Роли",
      languages: "Языки",
      links: "Ссылки",
      blacklist: "Чёрный список",
      tasks: "Задания",
      courts: "Суды",
      contracts: "Договоры",
      documents: "Документы",
      templates: "Шаблоны",
      shariahControl: "Шариатский контроль",
    },
    tasks: {
      title: "Задания",
      allTopics: "Все темы",
      empty: "Заданий нет.",
      errorLoad: "Не удалось загрузить задания.",
      open: "Открыто",
      take: "Взять",
      refresh: "Обновить",
      topic: "Тема",
      status: "Статус",
      mine: "Мои",
      unassigned: "Без исполнителя",
      details: "Детали",
      events: "История",
      comment: "Комментарий",
      addComment: "Добавить комментарий",
      notify: "Написать пользователю",
      send: "Отправить",
      updateStatus: "Изменить статус",
      viewSpec: "Открыть ТЗ",
      close: "Закрыть",
    },
    courts: {
      admin: {
        title: "Судебное дело",
        caseNumber: "Дело",
        status: "Статус",
        statusValue: "Статус",
        scholarName: "Учёный",
        scholarContact: "Контакт",
        scholarId: "ID учёного",
        update: "Обновить",
        statusUpdate: "Изменить",
        assignee: "Ответственный",
        category: "Категория",
        plaintiff: "Истец",
        defendant: "Ответчик",
        created: "Создано",
        evidence: "Доказательства",
        assignTitle: "Назначить ответственного",
        assignSelf: "Вы можете назначить только себя.",
        assignAction: "Назначить",
      },
      status: {
        open: "Открыто",
        in_progress: "В процессе",
        closed: "Завершено",
        cancelled: "Отменено",
      },
      category: {
        financial: "Финансовый спор",
        contract_breach: "Нарушение договора",
        property: "Имущество / аренда",
        goods: "Поставка / товар",
        services: "Услуги / работа",
        family: "Семейный вопрос",
        ethics: "Этический конфликт",
        unknown: "Неизвестная категория",
      },
    },
    contracts: {
      admin: {
        title: "Договор",
        status: "Статус",
        statusValue: "Статус",
        assignee: "Ответственный",
        created: "Создано",
        contractType: "Тип",
        contractTitle: "Название",
        owner: "Владелец",
        counterparty: "Контрагент",
        scholarName: "Учёный",
        scholarContact: "Контакт",
        scholarId: "ID учёного",
        update: "Обновить договор",
        statusUpdate: "Изменить",
        scholarSelect: "Выбрать учёного",
        scholarSelectPlaceholder: "Выберите из списка",
        scholarEmpty: "Список учёных пуст",
        assignTitle: "Назначить ответственного",
        assignSelf: "Вы можете назначить только себя.",
        assignAction: "Назначить",
        delete: "Удалить договор",
        deleteConfirm: "Удалить договор? Это действие нельзя отменить.",
        text: "Текст договора",
      },
      status: {
        draft: "Черновик",
        confirmed: "Подтверждён",
        sent_to_party: "Отправлен стороне",
        party_approved: "Подтверждён стороной",
        party_changes_requested: "Запрошены правки",
        signed: "Подписан",
        sent_to_scholar: "Отправлен учёному",
        scholar_send_failed: "Ошибка отправки учёному",
        sent: "Отправлен",
      },
    },
    roles: {
      title: "Роли и права",
      loading: "Загрузка ролей:",
      error: "Не удалось загрузить роли или админ-аккаунты.",
      rolesTitle: "Доступные роли",
      accountsTitle: "Аккаунты админов",
      username: "Логин",
      password: "Пароль",
      rolePick: "Стартовая роль (опционально)",
      rolePlaceholder: "Без роли при создании",
      telegram: "Telegram",
      create: "Создать аккаунт",
      creating: "Создаем...",
      created: "Аккаунт создан",
      createError: "Укажите логин и пароль.",
      assign: "Назначить",
      revoke: "Убрать",
      emptyRoles: "Ролей пока нет.",
      emptyAccounts: "Админ-аккаунтов пока нет.",
      account: "Аккаунт",
      status: "Статус",
      roleList: "Роли",
      actions: "Действия",
      notAllowed: "Нет прав на управление ролями.",
      ownerOnly: "Только владелец может управлять этой ролью.",
      labels: {
        admin_blacklist: "Админ черного списка",
        admin_documents: "Админ документов",
        admin_languages: "Админ языков",
        admin_links: "Админ ссылок",
        admin_templates: "Админ шаблонов",
        admin_work_items_view: "Задания: просмотр",
        admin_work_items_manage: "Задания: управление",
        admin_users: "Админ пользователей",
        tz_nikah: "ТЗ: Никях",
        tz_inheritance: "ТЗ: Наследство",
        tz_spouse_search: "ТЗ: Поиск супруга",
        tz_courts: "ТЗ: Суды",
        tz_contracts: "ТЗ: Договоры",
        tz_good_deeds: "ТЗ: Добрые дела",
        tz_execution: "ТЗ: Исполнение",
        shariah_chief: "Главный контролер",
        shariah_observer: "Шариатский наблюдатель",
        owner: "владелец",
        superadmin: "суперадмин",
        scholar: "Учёный",
      },
    },
    users: {
      loading: "Загрузка пользователей:",
      error: "Не удалось загрузить пользователей.",
      empty: "Пользователей пока нет.",
      columns: {
        status: "Статус",
        fullName: "Имя",
        telegramId: "Telegram ID",
        phone: "Телефон",
        created: "Создан",
        language: "Язык",
        role: "Роль",
        alive: "Активен",
        banned: "Заблокирован",
      },
      role: { user: "Пользователь" },
      actions: {
        ban: "Забанить",
        unban: "Разбанить",
        viewRequest: "Посмотреть запрос",
        approveUnban: "Разбанить",
        close: "Закрыть",
        attention: "Внимание",
        makeAdmin: "Сделать админом",
        delete: "Удалить",
      },
      adminForm: {
        username: "Логин админа",
        password: "Пароль",
        role: "Роль",
        create: "Создать админа",
        creating: "Создаем...",
        success: "Админ создан",
        error: "Не удалось создать админа. Проверьте поля.",
        update: "Сохранить изменения",
        updateSuccess: "Админ обновлен",
        updateError: "Не удалось обновить админа.",
        updateHint: "Обновите пароль или роль.",
      },
    },
    blacklist: {
      title: "черный список",
      description: "Управляйте записями черного списка и просматривайте жалобы и обращения.",
      loading: "Загрузка черного списка:",
      empty: "Записей в черном списке пока нет.",
      errorLoad: "Не удалось загрузить черный список.",
      errorLoadDetail: "Не удалось загрузить детали записи.",
      columns: {
        name: "Имя",
        phone: "Телефон",
        city: "Город",
        birthdate: "Дата рождения",
        isActive: "Статус",
        complaints: "Жалобы",
        appeals: "Обращения",
        added: "Добавлено",
        actions: "Действия",
      },
      status: {
        active: "Активен",
        inactive: "Неактивен",
      },
      actions: {
        refresh: "Обновить",
        activate: "Активировать",
        deactivate: "Деактивировать",
      },
      modal: {
        title: "Запись: {{name}}",
        status: "Статус",
        city: "Город",
        phone: "Телефон",
        birthdate: "Дата рождения",
        complaintsTitle: "Жалобы",
        complaintsEmpty: "Жалоб пока нет.",
        complaintHeader: "{{date}} — {{author}}",
        appealsTitle: "Обращения",
        appealsEmpty: "Обращений пока нет.",
        appealHeader: "{{date}} — {{author}}",
        attachmentsTitle: "Вложения",
        attachmentsEmpty: "Вложений нет.",
        attachmentDownload: "Скачать",
        close: "Закрыть",
      },
    },
    languages: {
      title: "Языки",
      loading: "Загрузка языков:",
      selectPrompt: "Выберите язык для редактирования переводов.",
      listDefaultMark: "по умолчанию",
      deleteButton: "Удалить",
      deleteConfirm: "Удалить язык {{code}}?",
      addLabel: "Добавить код языка",
      addPlaceholder: "например en",
      addButton: "Добавить",
      translationsTitle: "Переводы ({{code}})",
      translationsLoading: "Загрузка переводов:",
      translationIdentifier: "Ключ",
      translationValue: "Значение",
      translationEmpty: "Переводов пока нет.",
      translationAI: "Перевести (ИИ)",
      translationSave: "Сохранить",
      errorLoad: "Не удалось загрузить языки.",
      errorTranslations: "Не удалось загрузить переводы.",
      errorAdd: "Не удалось добавить язык.",
      errorDelete: "Не удалось удалить язык.",
      errorUpdate: "Не удалось обновить перевод.",
      infoAdded: "Язык {{code}} добавлен.",
      infoDeleted: "Язык {{code}} удалён.",
      infoSaved: "Сохранено {{identifier}} для {{code}}.",
    },
    links: {
      languageLabel: "Язык",
      description: "Настройте ссылки для выбранного языка.",
      defaultHint: "Оставьте пустым, чтобы использовать значение по умолчанию.",
      placeholder: "https://example.com",
      save: "Сохранить",
      reset: "Сбросить",
      successSave: "Сохранено.",
      successReset: "Сброшено к значению по умолчанию.",
      errorLoad: "Не удалось загрузить настройки ссылок.",
      errorSave: "Не удалось сохранить ссылку.",
      empty: "Слоты ссылок не настроены.",
      table: {
        slot: "Слот",
        url: "Ссылка",
      },
    },
    documents: {
      treeTitle: "Темы",
      uploadTitle: "Загрузить документ",
      selectLanguage: "Язык",
      selectFile: "Файл",
      uploadButton: "Загрузить",
      noLanguages: "Нет доступных языков. Сначала добавьте язык.",
      placeholder: "Выберите тему слева.",
      loading: "Загрузка документов:",
      empty: "Документов пока нет.",
      table: {
        filename: "Файл",
        language: "Язык",
        size: "Размер",
        uploaded: "Загружен",
      },
      actions: {
        view: "Открыть",
        replace: "Заменить",
        delete: "Удалить",
      },
      deleteConfirm: "Удалить {{name}}?",
      successUpload: "Загружено.",
      errorUpload: "Не удалось загрузить документ.",
      successReplace: "Заменено.",
      errorReplace: "Не удалось заменить документ.",
      successDelete: "Удалено.",
      errorDelete: "Не удалось удалить документ.",
      errorLoad: "Не удалось загрузить данные.",
    },
    contractTemplates: {
      treeTitle: "Категории",
      uploadTitle: "Загрузить шаблон",
      selectLanguage: "Язык",
      selectFile: "Файл",
      uploadButton: "Загрузить",
      noLanguages: "Нет доступных языков. Сначала добавьте язык.",
      placeholder: "Выберите группу шаблонов слева.",
      loading: "Загрузка шаблонов:",
      empty: "Шаблонов пока нет.",
      table: {
        filename: "Файл",
        language: "Язык",
        size: "Размер",
        uploaded: "Загружен",
      },
      actions: {
        view: "Открыть",
        replace: "Заменить",
        delete: "Удалить",
      },
      deleteConfirm: "Удалить {{name}}?",
      successUpload: "Загружено.",
      errorUpload: "Не удалось загрузить шаблон.",
      successReplace: "Заменено.",
      errorReplace: "Не удалось заменить шаблон.",
      successDelete: "Удалено.",
      errorDelete: "Не удалось удалить шаблон.",
      errorLoad: "Не удалось загрузить данные.",
    },
    shariahControl: {
      tabs: {
        deeds: "Добрые дела",
        needy: "Нуждающиеся",
        confirmations: "Подтверждения",
        applications: "Заявки админов",
      },
      empty: "Нет доступных разделов для вашей роли.",
    },
    goodDeeds: {
      title: "Добрые дела",
      listEmpty: "Добрых дел пока нет.",
      needyEmpty: "Заявок от нуждающихся нет.",
      confirmationsEmpty: "Подтверждений нет.",
      filters: {
        status: "Статус",
        city: "Город",
        country: "Страна",
        deedId: "ID доброго дела",
      },
      columns: {
        id: "ID",
        title: "Название",
        person: "Тип",
        user: "Пользователь",
        city: "Город",
        country: "Страна",
        status: "Статус",
        created: "Создано",
        goodDeed: "Доброе дело",
      },
      detail: {
        title: "Доброе дело",
        needyTitle: "Нуждающийся",
        confirmationTitle: "Подтверждение",
        user: "Пользователь",
        phone: "Телефон",
        email: "Email",
        description: "Описание",
        helpType: "Тип помощи",
        amount: "Сумма",
        comment: "Комментарий",
        status: "Статус",
        approvedCategory: "Категория",
        reviewComment: "Комментарий проверки",
        clarificationText: "Уточнение",
        clarificationAttachment: "Файл уточнения",
        created: "Создано",
        updated: "Обновлено",
        approvedAt: "Одобрено",
        completedAt: "Завершено",
        reason: "Причина",
        allowZakat: "Можно закят",
        allowFitr: "Можно фитр",
        sadaqaOnly: "Только садака",
        text: "Текст",
        attachment: "Вложение",
        goodDeed: "Доброе дело",
      },
      decision: {
        title: "Решение",
        status: "Решение",
        comment: "Комментарий",
        category: "Категория",
        submit: "Сохранить решение",
      },
      historyTitle: "История",
      downloadClarification: "Скачать уточнение",
      downloadAttachment: "Скачать вложение",
      statuses: {
        pending: "На проверке",
        needs_clarification: "Требует уточнения",
        approved: "Одобрено",
        in_progress: "В процессе",
        completed: "Завершено",
        rejected: "Отклонено",
      },
      decisionStatuses: {
        approved: "Одобрить",
        needs_clarification: "Запросить уточнение",
        rejected: "Отклонить",
      },
      categories: {
        zakat: "Разрешено для закята",
        fitr: "Разрешено для фитра",
        sadaqa: "Только садака",
      },
      helpTypes: {
        zakat: "Закят",
        fitr: "Фитр",
        sadaqa: "Садака",
        general: "Общая помощь",
      },
    },
    shariah: {
      title: "Заявки в шариатский контроль",
      listEmpty: "Заявок пока нет.",
      filters: {
        status: "Статус",
      },
      columns: {
        id: "ID",
        fullName: "ФИО",
        status: "Статус",
        country: "Страна",
        city: "Город",
        created: "Создано",
      },
      detail: {
        title: "Заявка",
        fullName: "ФИО",
        country: "Страна",
        city: "Город",
        educationPlace: "Где обучался",
        educationCompleted: "Закончил обучение",
        educationDetails: "Детали обучения",
        knowledgeAreas: "Направления знаний",
        experience: "Опыт",
        responsibility: "Ответственность принята",
        status: "Статус",
        meeting: "Знакомство",
        meetingType: "Тип",
        meetingLink: "Ссылка",
        meetingAt: "Дата и время",
        decisionComment: "Комментарий решения",
        assignedRoles: "Назначенные роли",
        user: "Пользователь",
        phone: "Телефон",
        email: "Email",
        created: "Создано",
        updated: "Обновлено",
      },
      schedule: {
        title: "Назначить встречу",
        type: "Тип встречи",
        link: "Ссылка",
        date: "Дата и время",
        submit: "Назначить",
      },
      decision: {
        title: "Решение",
        status: "Решение",
        comment: "Комментарий",
        roles: "Роли (1-2)",
        roleHint: "Выберите до 2 ролей.",
        submit: "Сохранить решение",
      },
      historyTitle: "История",
      statuses: {
        pending_intro: "Ожидает знакомства",
        meeting_scheduled: "Знакомство назначено",
        approved: "Назначен админом",
        observer: "Назначен наблюдателем",
        rejected: "Отказано",
      },
      meetingTypes: {
        video: "Видео встреча",
        audio: "Аудио встреча",
      },
      areas: {
        fiqh: "Фикх",
        contracts: "Договоры",
        courts: "Судебные вопросы",
        zakat: "Закят / садака",
        execution: "Исполнение решений",
        observer: "Контроль без решений",
      },
    },
  },
};
const RU_OVERRIDES = {
  tabs: {
    tasks: "Задания",
    courts: "Суды",
  },
  tasks: {
    title: "Задания",
    allTopics: "Все темы",
    empty: "Заданий нет.",
    errorLoad: "Не удалось загрузить задания.",
    open: "Открыть",
    take: "Взять",
    refresh: "Обновить",
    topic: "Тема",
    status: "Статус",
    statusTask: "Статус задачи",
    statusCase: "Статус дела",
    statusTask: "Статус задачи",
    statusCase: "Статус дела",
    mine: "Мои",
    unassigned: "Без исполнителя",
    details: "Детали",
    events: "События",
    comment: "Комментарий",
    addComment: "Добавить комментарий",
    notify: "Уведомить пользователя",
    send: "Отправить",
    updateStatus: "Изменить статус",
    viewSpec: "Открыть ТЗ",
    close: "Закрыть",
    id: "ID",
    kind: "Тип",
    priority: "Приоритет",
    targetUser: "Пользователь",
    created: "Создано",
    statuses: {
      new: "Новый",
      assigned: "Назначено",
      in_progress: "В процессе",
      waiting_user: "Ожидает пользователя",
      waiting_scholar: "Ожидает учёного",
      done: "Завершено",
      canceled: "Отменено",
    },
    kinds: {
      case_created: "Дело создано",
      needs_review: "Нужна проверка",
      scholar_request: "Запрос учёному",
      moderation_incident: "Инцидент модерации",
    },
  },
  courts: {
    admin: {
      title: "Судебное дело",
      caseNumber: "Дело",
      status: "Статус",
      statusValue: "Статус",
      scholarName: "Учёный",
      scholarContact: "Контакт",
      scholarId: "ID учёного",
      update: "Обновить",
      assignee: "Ответственный",
      category: "Категория",
      plaintiff: "Истец",
      defendant: "Ответчик",
      created: "Создано",
      evidence: "Доказательства",
      scholarSelect: "Выбрать учёного",
      scholarSelectPlaceholder: "Выберите из списка",
      scholarEmpty: "Список учёных пуст",
      assignTitle: "Назначить ответственного",
      assignSelf: "Вы можете назначить только себя.",
      assignAction: "Назначить",
      statusHint: "Статус дела влияет на карточку суда, статус задачи — на внутренний workflow.",
    },
    status: {
      open: "Открыто",
      in_progress: "В процессе",
      closed: "Завершено",
      cancelled: "Отменено",
    },
    category: {
      financial: "Финансовый спор",
      contract_breach: "Нарушение договора",
      property: "Имущество / аренда",
      goods: "Поставка / товар",
      services: "Услуги / работа",
      family: "Семейный вопрос",
      ethics: "Этический конфликт",
      unknown: "Неизвестная категория",
    },
  },
};
const TranslationContext = React.createContext({
  language: SUPPORTED_UI_LANGUAGES[0],
  setLanguage: () => {},
  t: (key) => key,
});

const resolveFromDict = (dictionary, path) => {
  if (!dictionary) {
    return undefined;
  }
  return path.reduce(
    (acc, segment) =>
      acc && acc[segment] !== undefined ? acc[segment] : undefined,
    dictionary,
  );
};

const interpolate = (template, params) =>
  template.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, token) =>
    Object.prototype.hasOwnProperty.call(params, token)
      ? params[token]
      : match,
  );

const TranslationProvider = ({ language, onChangeLanguage, children }) => {
  const t = useCallback(
    (key, params = {}) => {
      const path = key.split(".");
      const override =
        language === "ru" ? resolveFromDict(RU_OVERRIDES, path) : undefined;
      const phrase =
        override ??
        resolveFromDict(UI_TRANSLATIONS[language], path) ??
        resolveFromDict(UI_TRANSLATIONS.en, path) ??
        key;
      if (typeof phrase === "string") {
        return interpolate(phrase, params);
      }
      return phrase;
    },
    [language],
  );

  const setLanguage = useCallback(
    (nextLanguage) => {
      if (nextLanguage === language) {
        return;
      }
      if (SUPPORTED_UI_LANGUAGES.includes(nextLanguage)) {
        onChangeLanguage(nextLanguage);
      }
    },
    [language, onChangeLanguage],
  );

  const value = useMemo(
    () => ({
      language,
      setLanguage,
      t,
    }),
    [language, setLanguage, t],
  );

  return (
    <TranslationContext.Provider value={value}>
      {children}
    </TranslationContext.Provider>
  );
};

const useI18n = () => React.useContext(TranslationContext);

const LanguageSwitcher = ({ variant = "default" }) => {
  const { language, setLanguage, t } = useI18n();
  const isCompact = variant === "compact";

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.5rem",
        flexWrap: "wrap",
        justifyContent: "flex-end",
      }}
    >
      {SUPPORTED_UI_LANGUAGES.map((code) => {
        const active = language === code;
        return (
          <button
            key={code}
            type="button"
            style={{
              ...(active ? buttonStyle("primary") : buttonStyle("ghost")),
              padding: isCompact ? "0.35rem 0.75rem" : "0.45rem 1rem",
            }}
            onClick={() => setLanguage(code)}
            disabled={active}
          >
            {t(`languageNames.${code}`)}
          </button>
        );
      })}
    </div>
  );
};

const Card = ({ title, subtitle, actions, children }) => (
  <div style={LAYOUT.card}>
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: "1.5rem",
        marginBottom: "2rem",
      }}
    >
      <div>
        <h1
          style={{
            margin: 0,
            fontSize: "2rem",
            fontWeight: 700,
            color: COLORS.text,
          }}
        >
          {title}
        </h1>
        {subtitle ? (
          <p style={{ marginTop: "0.5rem", color: COLORS.secondaryText }}>
            {subtitle}
          </p>
        ) : null}
      </div>
      {actions ? <div>{actions}</div> : null}
    </div>
    {children}
  </div>
);

const Notice = ({ kind = "info", children }) => {
  const palette = {
    info: {
      backgroundColor: "#eef2ff",
      color: COLORS.primaryDark,
      borderColor: COLORS.border,
    },
    success: {
      backgroundColor: "#dcfce7",
      color: COLORS.success,
      borderColor: "#86efac",
    },
    error: {
      backgroundColor: "#fee2e2",
      color: COLORS.danger,
      borderColor: "#fca5a5",
    },
  };

  const style = palette[kind] || palette.info;

  return (
    <div
      style={{
        marginBottom: "1rem",
        padding: "0.75rem 1rem",
        borderRadius: "10px",
        border: `1px solid ${style.borderColor}`,
        backgroundColor: style.backgroundColor,
        color: style.color,
        fontSize: "0.95rem",
      }}
    >
      {children}
    </div>
  );
};

const Table = ({ columns, rows, emptyText, rowKey = "id", onRowClick }) => (
  <div
    style={{
      border: `1px solid ${COLORS.border}`,
      borderRadius: "12px",
      overflow: "hidden",
    }}
  >
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead style={{ backgroundColor: "#f1f5f9" }}>
        <tr>
          {columns.map((column) => (
            <th
              key={column.key}
              style={{
                textAlign: column.align || "left",
                padding: "0.9rem 1.1rem",
                fontSize: "0.85rem",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                color: COLORS.secondaryText,
                width: column.width,
              }}
            >
              {column.title}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td
              colSpan={columns.length}
              style={{
                padding: "1.25rem",
                textAlign: "center",
                color: COLORS.secondaryText,
              }}
            >
              {emptyText}
            </td>
          </tr>
        ) : (
          rows.map((row, index) => (
            <tr
              key={
                (typeof rowKey === "function"
                  ? rowKey(row)
                  : row[rowKey ?? "id"]) ?? index
              }
              style={{
                backgroundColor: index % 2 === 0 ? "#ffffff" : "#f8fafc",
                borderTop: `1px solid ${COLORS.border}`,
                cursor: onRowClick ? "pointer" : "default",
              }}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  style={{ padding: "0.9rem 1.1rem", fontSize: "0.97rem" }}
                >
                  {typeof column.render === "function"
                    ? column.render(row)
                    : row[column.key]}
                </td>
              ))}
            </tr>
          ))
        )}
      </tbody>
    </table>
  </div>
);
const Tabs = ({ active, onChange, tabs }) => {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
      {tabs.map((tab) => {
        const isActive = active === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            style={{
              ...(isActive ? buttonStyle("primary") : buttonStyle("ghost")),
              padding: "0.55rem 1.4rem",
            }}
            onClick={() => onChange(tab.key)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
};

const HistoryList = ({ items, t, language }) => {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) {
    return <div style={{ color: COLORS.secondaryText }}>{t("common.notAvailable")}</div>;
  }
  return (
    <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
      {list.map((item, index) => {
        const action = item?.action || item?.status || t("common.notAvailable");
        const status = item?.action && item?.status && item.status !== item.action ? item.status : "";
        const timestamp = item?.at ? formatDateTime(item.at, language) : t("common.notAvailable");
        return (
          <li key={`${item?.at || index}`} style={{ marginBottom: "0.6rem" }}>
            <strong>{action}</strong>
            {status ? <span> ({status})</span> : null}{" "}
            <span style={{ color: COLORS.secondaryText }}>{timestamp}</span>
            {item?.comment ? (
              <div style={{ color: COLORS.secondaryText, whiteSpace: "pre-wrap" }}>
                {item.comment}
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
};

const LoginForm = ({ onSubmit, loading, error }) => {
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = useCallback(
    (event) => {
      event.preventDefault();
      onSubmit(username.trim(), password);
    },
    [username, password, onSubmit],
  );

  return (
    <Card
      title={t("login.title")}
      subtitle={t("login.subtitle")}
      actions={<LanguageSwitcher variant="compact" />}
    >
      {error ? <Notice kind="error">{error}</Notice> : null}
      <form onSubmit={handleSubmit}>
        <label
          style={{
            display: "block",
            marginBottom: "0.5rem",
            color: COLORS.secondaryText,
          }}
        >
          {t("login.usernameLabel")}
        </label>
        <input
          type="text"
          style={{
            width: "100%",
            padding: "0.75rem 1rem",
            borderRadius: "10px",
            border: `1px solid ${COLORS.border}`,
            fontSize: "1rem",
            marginBottom: "1.25rem",
          }}
          placeholder={t("login.usernamePlaceholder")}
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          required
          autoComplete="username"
        />

        <label
          style={{
            display: "block",
            marginBottom: "0.5rem",
            color: COLORS.secondaryText,
          }}
        >
          {t("login.passwordLabel")}
        </label>
        <input
          type="password"
          style={{
            width: "100%",
            padding: "0.75rem 1rem",
            borderRadius: "10px",
            border: `1px solid ${COLORS.border}`,
            fontSize: "1rem",
            marginBottom: "1.5rem",
          }}
          placeholder={t("login.passwordPlaceholder")}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          autoComplete="current-password"
        />

        <button
          type="submit"
          style={{ ...buttonStyle("primary"), width: "100%" }}
          disabled={loading}
        >
          {loading ? t("login.submitting") : t("login.submit")}
        </button>
      </form>
    </Card>
  );
};

const OtpForm = ({ onSubmit, onBack, loading, error, username }) => {
  const { t } = useI18n();
  const [code, setCode] = useState("");

  const handleSubmit = useCallback(
    (event) => {
      event.preventDefault();
      onSubmit(code.trim());
    },
    [code, onSubmit],
  );

  return (
    <Card
      title={t("login.otpTitle")}
      subtitle={t("login.otpSubtitle", { username })}
      actions={<LanguageSwitcher variant="compact" />}
    >
      {error ? <Notice kind="error">{error}</Notice> : null}
      <form onSubmit={handleSubmit}>
        <label
          style={{
            display: "block",
            marginBottom: "0.5rem",
            color: COLORS.secondaryText,
          }}
        >
          {t("login.otpLabel")}
        </label>
        <input
          type="text"
          style={{
            width: "100%",
            padding: "0.75rem 1rem",
            borderRadius: "10px",
            border: `1px solid ${COLORS.border}`,
            fontSize: "1rem",
            marginBottom: "1.5rem",
          }}
          placeholder={t("login.otpPlaceholder")}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          required
          autoComplete="one-time-code"
        />
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            type="button"
            style={{ ...buttonStyle("ghost"), flex: 1 }}
            onClick={onBack}
            disabled={loading}
          >
            {t("common.cancel")}
          </button>
          <button
            type="submit"
            style={{ ...buttonStyle("primary"), flex: 1 }}
            disabled={loading}
          >
            {loading ? t("login.submitting") : t("login.otpSubmit")}
          </button>
        </div>
      </form>
    </Card>
  );
};

const UsersTab = ({ fetcher, roles, roleOptions }) => {
  const { t, language } = useI18n();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalUser, setModalUser] = useState(null);
  const [existingAdmin, setExistingAdmin] = useState(null);
  const [adminUsername, setAdminUsername] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminRole, setAdminRole] = useState("");
  const [adminMessage, setAdminMessage] = useState("");
  const roleSet = new Set(roles || []);
  const canManageUsers = roleSet.has("owner") || roleSet.has("superadmin") || roleSet.has("admin_users");
  const canDeleteUsers = roleSet.has("owner") || roleSet.has("superadmin");
  const canMakeAdmin = roleSet.has("owner") || roleSet.has("superadmin");

  useEffect(() => {
    let ignore = false;
    const load = async () => {
      try {
        setLoading(true);
        const response = await fetcher("/admin/users");
        const data = await response.json();
        if (!ignore) {
          const sorted = [...data].sort((a, b) => {
            const aReq = a.unban_requested_at ? new Date(a.unban_requested_at).getTime() : 0;
            const bReq = b.unban_requested_at ? new Date(b.unban_requested_at).getTime() : 0;
            if (aReq !== bReq) return bReq - aReq;
            const aC = a.created_at ? new Date(a.created_at).getTime() : 0;
            const bC = b.created_at ? new Date(b.created_at).getTime() : 0;
            return bC - aC;
          });
          setUsers(sorted);
          setError("");
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || t("users.error"));
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      ignore = true;
    };
  }, [fetcher, t]);

  const handleDelete = async (telegramId) => {
    if (!canDeleteUsers) return;
    if (!confirm(`${t("users.actions.delete")} ${telegramId}?`)) return;
    try {
      const response = await fetcher(`/admin/users/${telegramId}`, { method: "DELETE" });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || t("users.error"));
      }
      setUsers((prev) => prev.filter((u) => u.user_id !== telegramId));
      setModalUser(null);
    } catch (err) {
      setError(err.message || t("users.error"));
    }
  };

  const handleToggleBan = async (telegramId, nextBanned) => {
    if (!canManageUsers) return;
    try {
      const response = await fetcher(`/admin/users/${telegramId}/ban`, {
        method: "PATCH",
        body: JSON.stringify({ banned: nextBanned }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || t("users.error"));
      }
      const updated = await response.json();
      setUsers((prev) => {
        const next = prev.map((u) => (u.user_id === telegramId ? updated : u));
        next.sort((a, b) => {
          const aReq = a.unban_requested_at ? new Date(a.unban_requested_at).getTime() : 0;
          const bReq = b.unban_requested_at ? new Date(b.unban_requested_at).getTime() : 0;
          if (aReq !== bReq) return bReq - aReq;
          const aC = a.created_at ? new Date(a.created_at).getTime() : 0;
          const bC = b.created_at ? new Date(b.created_at).getTime() : 0;
          return bC - aC;
        });
        return next;
      });
      if (!nextBanned) setModalUser(null);
    } catch (err) {
      setError(err.message || t("users.error"));
    }
  };

  const columns = [
    {
      key: "user_id",
      title: t("users.columns.telegramId"),
      width: "140px",
      render: (row) => row.user_id ?? t("common.notAvailable"),
    },
    {
      key: "full_name",
      title: t("users.columns.fullName"),
      render: (row) => row.full_name || t("common.notAvailable"),
    },
    {
      key: "phone_number",
      title: t("users.columns.phone"),
      width: "160px",
      render: (row) => row.phone_number || t("common.notAvailable"),
    },
    {
      key: "role",
      title: t("users.columns.role"),
      width: "140px",
      render: (row) => row.role || t("users.role.user"),
    },
    {
      key: "banned",
      title: t("users.columns.banned"),
      width: "120px",
      render: (row) => (row.banned ? t("common.yes") : t("common.no")),
    },
    {
      key: "created_at",
      title: t("users.columns.created"),
      width: "210px",
      render: (row) =>
        row.created_at
          ? formatDateTime(row.created_at, language)
          : t("common.notAvailable"),
    },
  ];

  const onRowClick = (row) => {
    setModalUser(row);
    setAdminUsername(`user_${row.user_id}`);
    setAdminPassword("");
    setAdminRole("");
    setAdminMessage("");
    setExistingAdmin(null);
    if (canMakeAdmin) {
      fetcher("/admin/admin-accounts")
        .then((resp) => resp.json())
        .then((accounts) => {
          const found = (accounts || []).find((a) => String(a.telegram_id) === String(row.user_id));
          if (found) {
            setExistingAdmin(found);
            setAdminUsername(found.username || `user_${row.user_id}`);
            setAdminRole((found.roles && found.roles[0]) || "");
          }
        })
        .catch(() => {});
    }
  };

  if (loading) {
    return <div>{t("users.loading")}</div>;
  }

  if (error) {
    return <Notice kind="error">{error}</Notice>;
  }

  return (
    <>
      <Table
        columns={columns}
        rows={users}
        emptyText={t("users.empty")}
        rowKey="user_id"
        onRowClick={onRowClick}
      />
      {modalUser ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setModalUser(null)}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: "1.25rem 1.5rem",
              borderRadius: "12px",
              minWidth: "380px",
              maxWidth: "720px",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ marginTop: 0 }}>
              {t("users.actions.attention")} • {modalUser.full_name || modalUser.user_id}
            </h3>
            <div style={{ display: "grid", gap: "0.35rem", marginBottom: "1rem", color: COLORS.secondaryText }}>
              <span>{t("users.columns.telegramId")}: {modalUser.user_id}</span>
              <span>{t("users.columns.phone")}: {modalUser.phone_number || t("common.notAvailable")}</span>
              <span>{t("users.columns.role")}: {modalUser.role || t("users.role.user")}</span>
              <span>{t("users.columns.banned")}: {modalUser.banned ? t("common.yes") : t("common.no")}</span>
              <span>{t("users.columns.alive")}: {modalUser.is_alive ? t("common.yes") : t("common.no")}</span>
            </div>
            <div style={{ whiteSpace: "pre-wrap", marginBottom: "1rem", color: COLORS.secondaryText }}>
              {modalUser.unban_request_text ? modalUser.unban_request_text : t("common.notAvailable")}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                {canManageUsers ? (
                  <button
                    type="button"
                    style={buttonStyle("primary")}
                    onClick={() => handleToggleBan(modalUser.user_id, !modalUser.banned)}
                  >
                    {modalUser.banned ? t("users.actions.unban") : t("users.actions.ban")}
                  </button>
                ) : null}
                {canDeleteUsers ? (
                  <button
                    type="button"
                    style={buttonStyle("danger")}
                    onClick={() => handleDelete(modalUser.user_id)}
                  >
                    {t("users.actions.delete")}
                  </button>
                ) : null}
                <button type="button" style={buttonStyle("ghost")} onClick={() => setModalUser(null)}>
                  {t("users.actions.close")}
                </button>
              </div>
              {canMakeAdmin ? (
                <div
                  style={{
                    padding: "0.75rem",
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: "10px",
                    backgroundColor: "#f8fafc",
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                    gap: "0.5rem",
                  }}
                >
                  <strong style={{ gridColumn: "1/-1" }}>
                    {existingAdmin ? t("roles.accountsTitle") : t("users.actions.makeAdmin")}
                  </strong>
                  {existingAdmin ? (
                    <div style={{ gridColumn: "1/-1", color: COLORS.secondaryText }}>
                      {existingAdmin.username} ({(existingAdmin.roles || []).join(", ") || "-"})
                    </div>
                  ) : null}
                  <input
                    type="text"
                    placeholder={t("users.adminForm.username")}
                    value={adminUsername}
                    onChange={(e) => setAdminUsername(e.target.value)}
                    style={{ padding: "0.5rem", borderRadius: "8px", border: `1px solid ${COLORS.border}` }}
                  />
                  <input
                    type="password"
                    placeholder={t("users.adminForm.password")}
                    value={adminPassword}
                    onChange={(e) => setAdminPassword(e.target.value)}
                    style={{ padding: "0.5rem", borderRadius: "8px", border: `1px solid ${COLORS.border}` }}
                  />
                  <select
                    value={adminRole}
                    onChange={(e) => setAdminRole(e.target.value)}
                    style={{ padding: "0.5rem", borderRadius: "8px", border: `1px solid ${COLORS.border}` }}
                  >
                    <option value="">{t("users.adminForm.role")}</option>
                    {(roleOptions || []).map((r) => (
                      <option key={r.slug} value={r.slug}>
                        {r.slug}
                      </option>
                    ))}
                  </select>
                  {existingAdmin ? (
                    <>
                      <div style={{ gridColumn: "1/-1", color: COLORS.secondaryText }}>
                        {t("users.adminForm.updateHint")}
                      </div>
                      <div style={{ gridColumn: "1/-1", color: COLORS.secondaryText }}>
                        {t("roles.actions")}: {existingAdmin.roles.join(", ") || "-"}
                      </div>
                      <button
                        type="button"
                        style={buttonStyle("primary")}
                        onClick={async () => {
                          try {
                            setAdminMessage("");
                            const pwd = (adminPassword || "").trim();
                            const payload = {};
                            if (pwd) payload.password = pwd;
                            if (adminRole) payload.roles = [adminRole];
                            if (!Object.keys(payload).length) {
                              setAdminMessage(t("users.adminForm.updateError"));
                              return;
                            }
                            const resp = await fetcher(`/admin/admin-accounts/${existingAdmin.id}`, {
                              method: "PATCH",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify(payload),
                            });
                            if (!resp.ok) {
                              const text = await resp.text();
                              throw new Error(`HTTP ${resp.status}: ${text || resp.statusText || ""}`);
                            }
                            const updated = await resp.json();
                            setExistingAdmin(updated);
                            setAdminMessage(t("users.adminForm.updateSuccess"));
                            setAdminPassword("");
                          } catch (err) {
                            const msg =
                              err instanceof Error && err.message
                                ? err.message
                                : String(err || t("users.adminForm.updateError"));
                            setAdminMessage(msg);
                          }
                        }}
                      >
                        {t("users.adminForm.update")}
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      style={buttonStyle("primary")}
                      onClick={async () => {
                        try {
                          setAdminMessage("");
                          const trimmedUsername = (adminUsername || "").trim();
                          const pwd = (adminPassword || "").trim();
                          if (!trimmedUsername) {
                            setAdminMessage(t("users.adminForm.error"));
                            return;
                          }
                          const payload = {
                            username: trimmedUsername,
                            password: pwd,
                            telegram_id: modalUser.user_id,
                          };
                          if (adminRole) payload.roles = [adminRole];
                          const resp = await fetcher("/admin/admin-accounts", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(payload),
                          });
                          if (!resp.ok) {
                            const text = await resp.text();
                            throw new Error(`HTTP ${resp.status}: ${text || resp.statusText || ""}`);
                          }
                          const created = await resp.json();
                          setAdminMessage(t("users.adminForm.success"));
                          setExistingAdmin(created);
                          setAdminRole((created.roles && created.roles[0]) || "");
                        } catch (err) {
                          const msg =
                            err instanceof Error && err.message
                              ? err.message
                              : String(err || t("users.adminForm.error"));
                          setAdminMessage(msg);
                        }
                      }}
                    >
                      {t("users.adminForm.create")}
                    </button>
                  )}
                  {adminMessage ? <Notice kind="info">{String(adminMessage)}</Notice> : null}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
};
const LanguagesTab = ({ fetcher }) => {
  const { t } = useI18n();
  const [languages, setLanguages] = useState([]);
  const [selected, setSelected] = useState("");
  const [translations, setTranslations] = useState([]);
  const [loadingLanguages, setLoadingLanguages] = useState(true);
  const [loadingTranslations, setLoadingTranslations] = useState(false);
  const [error, setError] = useState("");
  const [infoMessage, setInfoMessage] = useState("");
  const [newLanguage, setNewLanguage] = useState("");
  const [editValues, setEditValues] = useState({});

  const loadLanguages = useCallback(async () => {
    setLoadingLanguages(true);
    try {
      const response = await fetcher("/admin/languages");
      const data = await response.json();
      setLanguages(data);
      if (data.length) {
        if (!selected) {
          const defaultLanguage =
            data.find((item) => item.is_default)?.code ?? data[0].code;
          setSelected(defaultLanguage);
        } else if (!data.find((item) => item.code === selected)) {
          setSelected(data[0].code);
        }
      } else {
        setSelected("");
      }
      setError("");
    } catch (err) {
      setError(err.message || t("languages.errorLoad"));
    } finally {
      setLoadingLanguages(false);
    }
  }, [fetcher, selected, t]);

  useEffect(() => {
    loadLanguages();
  }, [loadLanguages]);

  useEffect(() => {
    if (!selected) {
      setTranslations([]);
      return;
    }

    let cancelled = false;
    const loadTranslations = async () => {
      setLoadingTranslations(true);
      try {
        const response = await fetcher(`/admin/translations?language=${selected}`);
        const data = await response.json();
        if (!cancelled) {
          setTranslations(data);
          setEditValues({});
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || t("languages.errorTranslations"));
        }
      } finally {
        if (!cancelled) {
          setLoadingTranslations(false);
        }
      }
    };

    loadTranslations();
    return () => {
      cancelled = true;
    };
  }, [selected, fetcher, t]);

  const handleAddLanguage = async (event) => {
    event.preventDefault();
    if (!newLanguage.trim()) {
      return;
    }
    try {
      const response = await fetcher("/admin/languages", {
        method: "POST",
        body: JSON.stringify({
          code: newLanguage.trim(),
          is_default: false,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || t("languages.errorAdd"));
      }
      const created = await response.json();
      setNewLanguage("");
      await loadLanguages();
      setSelected(created.code);
      setInfoMessage(t("languages.infoAdded", { code: created.code }));
    } catch (err) {
      setError(err.message || t("languages.errorAdd"));
    }
  };

  const handleDeleteLanguage = async (code) => {
    if (!window.confirm(t("languages.deleteConfirm", { code }))) {
      return;
    }
    try {
      const response = await fetcher(`/admin/languages/${code}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || t("languages.errorDelete"));
      }
      await loadLanguages();
      if (selected === code) {
        setSelected("");
      }
      setInfoMessage(t("languages.infoDeleted", { code }));
    } catch (err) {
      setError(err.message || t("languages.errorDelete"));
    }
  };

  const handleTranslationChange = (identifier, value) => {
    setEditValues((prev) => ({ ...prev, [identifier]: value }));
  };

  const handleSaveTranslation = async (identifier) => {
    if (!selected) {
      return;
    }
    const value = Object.prototype.hasOwnProperty.call(editValues, identifier)
      ? editValues[identifier]
      : translations.find((item) => item.identifier === identifier)?.value ?? "";
    try {
      const response = await fetcher("/admin/translations", {
        method: "PUT",
        body: JSON.stringify({
          payload: {
            language: selected,
            identifier,
            value,
          },
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || t("languages.errorUpdate"));
      }
      const updated = await response.json();
      setTranslations((prev) =>
        prev.map((item) =>
          item.identifier === updated.identifier ? updated : item,
        ),
      );
      setEditValues((prev) => {
        const next = { ...prev };
        delete next[identifier];
        return next;
      });
      setInfoMessage(
        t("languages.infoSaved", {
          identifier,
          code: selected.toUpperCase(),
        }),
      );
    } catch (err) {
      setError(err.message || t("languages.errorUpdate"));
    }
  };

  const handleAiTranslation = async (identifier) => {
    if (!selected) return;
    try {
      const response = await fetcher("/admin/translations/ai", {
        method: "POST",
        body: JSON.stringify({
          payload: { language: selected, identifier },
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || t("languages.errorUpdate"));
      }
      const updated = await response.json();
      setTranslations((prev) =>
        prev.map((item) =>
          item.identifier === updated.identifier ? updated : item,
        ),
      );
      setEditValues((prev) => {
        const next = { ...prev };
        delete next[identifier];
        return next;
      });
      setInfoMessage(
        t("languages.infoSaved", {
          identifier,
          code: selected.toUpperCase(),
        }),
      );
    } catch (err) {
      setError(err.message || t("languages.errorUpdate"));
    }
  };

  return (
    <div style={{ display: "flex", gap: "2rem" }}>
      <div style={{ width: "240px" }}>
        <h2
          style={{
            fontSize: "1.1rem",
            marginBottom: "0.8rem",
            color: COLORS.text,
          }}
        >
          {t("languages.title")}
        </h2>
        {loadingLanguages ? (
          <div>{t("languages.loading")}</div>
        ) : (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "0.6rem",
            }}
          >
            {languages.map((lang) => {
              const isActive = lang.code === selected;
              return (
                <div
                  key={lang.code}
                  style={{
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: "10px",
                    padding: "0.55rem 0.75rem",
                    cursor: "pointer",
                    backgroundColor: isActive
                      ? "rgba(37, 99, 235, 0.08)"
                      : "#ffffff",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "0.5rem",
                  }}
                  onClick={() => setSelected(lang.code)}
                >
                  <span>
                    {lang.code.toUpperCase()}
                      {lang.is_default
                        ? ` · ${t("languages.listDefaultMark")}`
                        : ""}
                  </span>
                  {!lang.is_default ? (
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleDeleteLanguage(lang.code);
                      }}
                      style={{ ...buttonStyle("ghost"), padding: "0.3rem 0.6rem" }}
                    >
                      {t("languages.deleteButton")}
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}

        <form onSubmit={handleAddLanguage} style={{ marginTop: "1.5rem" }}>
          <label
            style={{
              display: "block",
              marginBottom: "0.5rem",
              fontSize: "0.9rem",
              color: COLORS.secondaryText,
            }}
          >
            {t("languages.addLabel")}
          </label>
          <input
            type="text"
            placeholder={t("languages.addPlaceholder")}
            value={newLanguage}
            onChange={(event) => setNewLanguage(event.target.value)}
            style={{
              width: "100%",
              padding: "0.6rem 0.8rem",
              borderRadius: "8px",
              border: `1px solid ${COLORS.border}`,
              marginBottom: "0.75rem",
            }}
          />
          <button
            type="submit"
            style={{ ...buttonStyle("primary"), width: "100%" }}
          >
            {t("languages.addButton")}
          </button>
        </form>
      </div>

      <div style={{ flex: 1 }}>
        {error ? <Notice kind="error">{error}</Notice> : null}
        {infoMessage ? <Notice kind="success">{infoMessage}</Notice> : null}

        {selected ? (
          <>
            <h2 style={{ fontSize: "1.1rem", marginBottom: "0.8rem" }}>
              {t("languages.translationsTitle", {
                code: selected.toUpperCase(),
              })}
            </h2>
            {loadingTranslations ? (
              <div>{t("languages.translationsLoading")}</div>
            ) : (
              <Table
                columns={[
                  { key: "identifier", title: t("languages.translationIdentifier") },
                  {
                    key: "value",
                    title: t("languages.translationValue"),
                  render: (row) => (
                    <div
                      style={{
                        display: "flex",
                        gap: "0.8rem",
                        alignItems: "center",
                      }}
                    >
                      <input
                        type="text"
                        value={
                          Object.prototype.hasOwnProperty.call(
                            editValues,
                            row.identifier,
                          )
                            ? editValues[row.identifier]
                            : row.value ?? ""
                        }
                        onChange={(event) =>
                          handleTranslationChange(row.identifier, event.target.value)
                        }
                        style={{
                          flex: 1,
                          padding: "0.6rem 0.75rem",
                          borderRadius: "8px",
                          border: `1px solid ${COLORS.border}`,
                        }}
                      />
                      <button
                        type="button"
                        style={{ ...buttonStyle("ghost"), padding: "0.5rem 0.8rem" }}
                        onClick={() => handleAiTranslation(row.identifier)}
                        disabled={!selected || selected === "dev"}
                      >
                        {t("languages.translationAI")}
                      </button>
                      <button
                        type="button"
                        style={{
                          ...buttonStyle("primary"),
                          padding: "0.5rem 0.8rem",
                        }}
                        onClick={() => handleSaveTranslation(row.identifier)}
                      >
                        {t("languages.translationSave")}
                      </button>
                    </div>
                  ),
                },
                ]}
                rows={translations}
                emptyText={t("languages.translationEmpty")}
                rowKey="identifier"
              />
            )}
          </>
        ) : (
          <div>{t("languages.selectPrompt")}</div>
        )}
      </div>
    </div>
  );
};
const LinksTab = ({ fetcher }) => {
  const { t, language } = useI18n();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [data, setData] = useState(null);
  const [selectedLanguage, setSelectedLanguage] = useState("");
  const [editValues, setEditValues] = useState({});
  const [savingSlug, setSavingSlug] = useState("");

  const loadSettings = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetcher("/admin/link-settings");
      const payload = await response.json();
      setData(payload);
      setError("");
      if (payload.languages?.length) {
        const initial = payload.languages[0].code;
        setSelectedLanguage((prev) =>
          prev && payload.languages.some((item) => item.code === prev)
            ? prev
            : initial,
        );
      } else {
        setSelectedLanguage("");
      }
    } catch (err) {
      setError(err.message || t("links.errorLoad"));
    } finally {
      setLoading(false);
    }
  }, [fetcher, t]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (!data || !selectedLanguage) {
      setEditValues({});
      return;
    }
    const next = {};
    for (const slot of data.slots || []) {
      next[slot.slug] = data.links?.[slot.slug]?.[selectedLanguage] ?? "";
    }
    setEditValues(next);
  }, [data, selectedLanguage]);

  const handleChangeValue = (slug, value) => {
    setEditValues((prev) => ({ ...prev, [slug]: value }));
  };

  const submitChange = async (slug, url) => {
    setSavingSlug(slug);
    try {
      const response = await fetcher(`/admin/link-settings/${slug}`, {
        method: "PUT",
        body: JSON.stringify({
          language: selectedLanguage,
          url,
        }),
      });
      const payload = await response.json();
      setData((prev) => {
        if (!prev) {
          return prev;
        }
        const nextLinks = { ...(prev.links || {}) };
        nextLinks[slug] = {
          ...(nextLinks[slug] || {}),
          ...payload.links,
        };
        return {
          ...prev,
          links: nextLinks,
        };
      });
      setMessage(url ? t("links.successSave") : t("links.successReset"));
      setError("");
    } catch (err) {
      setError(err.message || t("links.errorSave"));
      setMessage("");
    } finally {
      setSavingSlug("");
    }
  };

  if (loading) {
    return <div>{t("common.loading")}</div>;
  }

  if (error && !data) {
    return <Notice kind="error">{error}</Notice>;
  }

  if (!data?.slots?.length) {
    return <div>{t("links.empty")}</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {error ? <Notice kind="error">{error}</Notice> : null}
      {message ? <Notice kind="success">{message}</Notice> : null}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "1rem",
          flexWrap: "wrap",
        }}
      >
        <div style={{ fontWeight: 600 }}>{t("links.languageLabel")}:</div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {(data.languages || []).map((lang) => {
            const isActive = lang.code === selectedLanguage;
            return (
              <button
                key={lang.code}
                type="button"
                style={{
                  ...(isActive ? buttonStyle("primary") : buttonStyle("ghost")),
                  padding: "0.4rem 1rem",
                }}
                onClick={() => setSelectedLanguage(lang.code)}
              >
                {lang.code.toUpperCase()}
              </button>
            );
          })}
        </div>
      </div>

      <p style={{ color: COLORS.secondaryText }}>
        {t("links.description")} {t("links.defaultHint")}
      </p>

      <Table
        columns={[
          {
            key: "slot",
            title: t("links.table.slot"),
            render: (row) =>
              row.titles?.[language] ?? row.titles?.en ?? row.slug,
          },
          {
            key: "url",
            title: t("links.table.url"),
            render: (row) => (
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "0.75rem",
                  alignItems: "center",
                }}
              >
                <input
                  type="url"
                  value={editValues[row.slug] ?? ""}
                  onChange={(event) =>
                    handleChangeValue(row.slug, event.target.value)
                  }
                  placeholder={t("links.placeholder")}
                  style={{
                    flex: "1 1 320px",
                    padding: "0.6rem 0.8rem",
                    borderRadius: "8px",
                    border: `1px solid ${COLORS.border}`,
                  }}
                />
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    type="button"
                    style={buttonStyle("primary")}
                    onClick={() =>
                      submitChange(row.slug, (editValues[row.slug] || "").trim())
                    }
                    disabled={savingSlug === row.slug || !selectedLanguage}
                  >
                    {t("links.save")}
                  </button>
                  <button
                    type="button"
                    style={buttonStyle("ghost")}
                    onClick={() => submitChange(row.slug, "")}
                    disabled={savingSlug === row.slug || !selectedLanguage}
                  >
                    {t("links.reset")}
                  </button>
                </div>
              </div>
            ),
          },
        ]}
        rows={data.slots || []}
        emptyText={t("links.empty")}
        rowKey={(row) => row.slug}
      />
    </div>
  );
};
const DocumentManager = ({ fetcher, config }) => {
  const { translationBase, treeEndpoint, itemListKey } = config;
  const { t, language } = useI18n();
  const [tree, setTree] = useState([]);
  const [selectedTopic, setSelectedTopic] = useState("");
  const [documents, setDocuments] = useState([]);
  const [languages, setLanguages] = useState([]);
  const [loadingTree, setLoadingTree] = useState(true);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [loadingLanguages, setLoadingLanguages] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [uploadLanguage, setUploadLanguage] = useState("");
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [replacingId, setReplacingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const fileInputs = useRef({});

  const translate = useCallback(
    (suffix, params = {}) => t(`${translationBase}.${suffix}`, params),
    [t, translationBase],
  );

  const loadTree = useCallback(async () => {
    setLoadingTree(true);
    try {
      const response = await fetcher(treeEndpoint);
      const payload = await response.json();
      setTree(payload.categories || []);
      setError("");
    } catch (err) {
      setError(err.message || translate("errorLoad"));
    } finally {
      setLoadingTree(false);
    }
  }, [fetcher, treeEndpoint, translate]);

  const loadLanguages = useCallback(async () => {
    setLoadingLanguages(true);
    try {
      const response = await fetcher("/admin/languages");
      const payload = await response.json();
      setLanguages(payload);
      if (payload.length) {
        setUploadLanguage((prev) =>
          prev && payload.some((item) => item.code === prev)
            ? prev
            : payload[0].code,
        );
      } else {
        setUploadLanguage("");
      }
    } catch (err) {
      setError(err.message || t("languages.errorLoad"));
    } finally {
      setLoadingLanguages(false);
    }
  }, [fetcher, t]);

  const loadDocuments = useCallback(
    async (topic) => {
      if (!topic) {
        setDocuments([]);
        return;
      }
      setLoadingDocuments(true);
      try {
        const response = await fetcher(`/admin/documents?topic=${topic}`);
        const payload = await response.json();
        setDocuments(payload);
        setError("");
      } catch (err) {
        setError(err.message || translate("errorLoad"));
      } finally {
        setLoadingDocuments(false);
      }
    },
    [fetcher, translate],
  );

  useEffect(() => {
    loadTree();
    loadLanguages();
  }, [loadTree, loadLanguages]);

  useEffect(() => {
    loadDocuments(selectedTopic);
  }, [loadDocuments, selectedTopic]);

  const findTopicTitle = (topicItem) =>
    topicItem?.titles?.[language] ?? topicItem?.titles?.en ?? topicItem?.topic ?? "";

  const findCategoryTitle = (categoryItem) =>
    categoryItem.titles?.[language] ??
    categoryItem.titles?.en ??
    categoryItem.category;

  const handleUpload = async (event) => {
    event.preventDefault();
    if (!selectedTopic || !uploadLanguage || !uploadFile) {
      return;
    }
    const formData = new FormData();
    formData.append("topic", selectedTopic);
    formData.append("language", uploadLanguage);
    formData.append("file", uploadFile);

    setUploading(true);
    try {
      await fetcher("/admin/documents", {
        method: "POST",
        body: formData,
      });
      setUploadFile(null);
      setMessage(translate("successUpload"));
      setError("");
      await loadDocuments(selectedTopic);
    } catch (err) {
      setError(err.message || translate("errorUpload"));
      setMessage("");
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (doc) => {
    try {
      const response = await fetcher(`/admin/documents/${doc.id}/download`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = doc.filename || `document-${doc.id}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || translate("errorLoad"));
    }
  };

  const handleReplace = async (docId, file) => {
    if (!file) {
      return;
    }
    setReplacingId(docId);
    const formData = new FormData();
    formData.append("file", file);
    try {
      await fetcher(`/admin/documents/${docId}`, {
        method: "PUT",
        body: formData,
      });
      setMessage(translate("successReplace"));
      setError("");
      await loadDocuments(selectedTopic);
    } catch (err) {
      setError(err.message || translate("errorReplace"));
      setMessage("");
    } finally {
      setReplacingId(null);
    }
  };

  const handleDelete = async (doc) => {
    if (!window.confirm(translate("deleteConfirm", { name: doc.filename }))) {
      return;
    }

    setDeletingId(doc.id);
    try {
      await fetcher(`/admin/documents/${doc.id}`, { method: "DELETE" });
      setMessage(translate("successDelete"));
      setError("");
      await loadDocuments(selectedTopic);
    } catch (err) {
      setError(err.message || translate("errorDelete"));
      setMessage("");
    } finally {
      setDeletingId(null);
    }
  };

  const renderTopicList = () => {
    if (loadingTree) {
      return <div>{t("common.loading")}</div>;
    }
    if (!tree.length) {
      return <div>{translate("placeholder")}</div>;
    }
    return tree.map((category) => (
      <div key={category.category} style={{ marginBottom: "1rem" }}>
        <div
          style={{
            fontWeight: 600,
            marginBottom: "0.4rem",
            color: COLORS.secondaryText,
          }}
        >
          {findCategoryTitle(category)}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
          {(category[itemListKey] || []).map((topic) => {
            const topicKey = topic.topic;
            const isActive = selectedTopic === topicKey;
            return (
              <button
                key={topicKey}
                type="button"
                style={{
                  ...(isActive ? buttonStyle("primary") : buttonStyle("ghost")),
                  justifyContent: "flex-start",
                  padding: "0.45rem 0.8rem",
                }}
                onClick={() => setSelectedTopic(topicKey)}
              >
                {findTopicTitle(topic)}
              </button>
            );
          })}
        </div>
      </div>
    ));
  };

  const renderDocumentsTable = () => {
    const renderNotice = (text) => (
      <div
        style={{
          padding: "1.25rem",
          borderRadius: "12px",
          border: `1px solid ${COLORS.border}`,
          backgroundColor: "#f8fafc",
        }}
      >
        {text}
      </div>
    );

    if (!selectedTopic) {
      return renderNotice(translate("placeholder"));
    }
    if (loadingDocuments) {
      return renderNotice(translate("loading"));
    }
    if (!documents.length) {
      return renderNotice(translate("empty"));
    }

    return (
      <Table
        columns={[
          {
            key: "filename",
            title: translate("table.filename"),
            render: (row) => row.filename || t("common.notAvailable"),
          },
          {
            key: "language_code",
            title: translate("table.language"),
            render: (row) => (row.language_code || "").toUpperCase(),
          },
          {
            key: "size",
            title: translate("table.size"),
            render: (row) => formatBytes(row.size),
          },
          {
            key: "uploaded_at",
            title: translate("table.uploaded"),
            render: (row) => formatDateTime(row.uploaded_at, language),
          },
          {
            key: "actions",
            title: t("common.actions"),
            render: (row) => (
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "0.4rem",
                }}
              >
                <button
                  type="button"
                  style={buttonStyle("ghost")}
                  onClick={() => handleDownload(row)}
                >
                  {translate("actions.view")}
                </button>
                <button
                  type="button"
                  style={buttonStyle("ghost")}
                  onClick={() => fileInputs.current[row.id]?.click()}
                  disabled={replacingId === row.id}
                >
                  {replacingId === row.id
                    ? t("common.loading")
                    : translate("actions.replace")}
                </button>
                <input
                  type="file"
                  style={{ display: "none" }}
                  ref={(node) => {
                    fileInputs.current[row.id] = node;
                  }}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.target.value = "";
                    if (file) {
                      handleReplace(row.id, file);
                    }
                  }}
                />
                <button
                  type="button"
                  style={buttonStyle("danger")}
                  onClick={() => handleDelete(row)}
                  disabled={deletingId === row.id}
                >
                  {deletingId === row.id
                    ? t("common.loading")
                    : translate("actions.delete")}
                </button>
              </div>
            ),
          },
        ]}
        rows={documents}
        emptyText={translate("empty")}
        rowKey="id"
      />
    );
  };

  return (
    <div style={{ display: "flex", gap: "2.5rem" }}>
      <aside style={{ width: "280px" }}>
        <h2
          style={{
            fontSize: "1.1rem",
            marginBottom: "0.8rem",
            color: COLORS.text,
          }}
        >
          {translate("treeTitle")}
        </h2>
        {renderTopicList()}
      </aside>
      <section style={{ flex: 1 }}>
        {error ? <Notice kind="error">{error}</Notice> : null}
        {message ? <Notice kind="success">{message}</Notice> : null}

        <div
          style={{
            marginBottom: "1.5rem",
            padding: "1.25rem 1.5rem",
            borderRadius: "12px",
            border: `1px solid ${COLORS.border}`,
            backgroundColor: "#f8fafc",
          }}
        >
          <h3
            style={{
              marginTop: 0,
              marginBottom: "1rem",
              fontSize: "1rem",
              fontWeight: 600,
            }}
          >
            {translate("uploadTitle")}
          </h3>
          <form
            onSubmit={handleUpload}
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "0.75rem",
              alignItems: "center",
            }}
          >
            <div>
              <label
                style={{
                  display: "block",
                  marginBottom: "0.3rem",
                  fontSize: "0.85rem",
                  color: COLORS.secondaryText,
                }}
              >
                {translate("selectLanguage")}
              </label>
              <select
                value={uploadLanguage}
                onChange={(event) => setUploadLanguage(event.target.value)}
                style={{
                  padding: "0.6rem 0.8rem",
                  borderRadius: "8px",
                  border: `1px solid ${COLORS.border}`,
                  minWidth: "120px",
                }}
                disabled={loadingLanguages || !languages.length}
              >
                {(languages || []).map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.code.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                style={{
                  display: "block",
                  marginBottom: "0.3rem",
                  fontSize: "0.85rem",
                  color: COLORS.secondaryText,
                }}
              >
                {translate("selectFile")}
              </label>
              <input
                type="file"
                onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
              />
            </div>
            <button
              type="submit"
              style={buttonStyle("primary")}
              disabled={
                uploading ||
                !selectedTopic ||
                !uploadLanguage ||
                !uploadFile ||
                !languages.length
              }
            >
              {uploading ? t("common.loading") : translate("uploadButton")}
            </button>
          </form>
          {!languages.length ? (
            <p style={{ marginTop: "0.75rem", color: COLORS.secondaryText }}>
              {translate("noLanguages")}
            </p>
          ) : null}
        </div>

        {renderDocumentsTable()}
      </section>
    </div>
  );
};

const BlacklistTab = ({ fetcher }) => {
  const { t, language } = useI18n();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [entryDetail, setEntryDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const formatBirthdate = useCallback(
    (value) => {
      if (!value) {
        return t("common.notAvailable");
      }
      try {
        return new Intl.DateTimeFormat(language || "en", {
          dateStyle: "medium",
        }).format(new Date(value));
      } catch (err) {
        return value;
      }
    },
    [language, t],
  );

  const loadEntries = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetcher("/admin/blacklist");
      const payload = await response.json();
      setEntries(payload);
    } catch (err) {
      setError(err.message || t("blacklist.errorLoad"));
    } finally {
      setLoading(false);
    }
  }, [fetcher, t]);

  const loadEntryDetail = useCallback(
    async (entryId) => {
      setDetailLoading(true);
      setDetailError("");
      try {
        const response = await fetcher(`/admin/blacklist/${entryId}`);
        const payload = await response.json();
        setEntryDetail(payload);
      } catch (err) {
        setDetailError(err.message || t("blacklist.errorLoadDetail"));
      } finally {
        setDetailLoading(false);
      }
    },
    [fetcher, t],
  );

  useEffect(() => {
    loadEntries();
  }, [loadEntries]);

  useEffect(() => {
    if (selectedId != null) {
      loadEntryDetail(selectedId);
    }
  }, [selectedId, loadEntryDetail]);

  const handleRefresh = useCallback(() => {
    loadEntries();
    if (selectedId != null) {
      loadEntryDetail(selectedId);
    }
  }, [loadEntries, loadEntryDetail, selectedId]);

  const handleRowClick = useCallback((row) => {
    setEntryDetail(null);
    setDetailError("");
    setSelectedId(row.id);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedId(null);
    setEntryDetail(null);
    setDetailError("");
  }, []);

  const handleToggleStatus = useCallback(
    async (entryId, nextStatus) => {
      setUpdatingStatus(true);
      setDetailError("");
      try {
        await fetcher(`/admin/blacklist/${entryId}/status`, {
          method: "POST",
          body: JSON.stringify({ is_active: nextStatus }),
        });
        const response = await fetcher(`/admin/blacklist/${entryId}`);
        const payload = await response.json();
        setEntryDetail(payload);
        setEntries((prev) =>
          prev.map((item) => (item.id === payload.id ? { ...item, ...payload } : item)),
        );
      } catch (err) {
        setDetailError(err.message || t("blacklist.errorLoadDetail"));
      } finally {
        setUpdatingStatus(false);
      }
    },
    [fetcher, t],
  );

  const handleDownloadMedia = useCallback(
    async (kind, parentId, media) => {
      try {
        const path =
          kind === "complaint"
            ? `/admin/blacklist/complaints/${parentId}/media/${media.id}`
            : `/admin/blacklist/appeals/${parentId}/media/${media.id}`;
        const response = await fetcher(path);
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = media.filename || "attachment";
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      } catch (err) {
        console.error(err);
        setDetailError(err.message || t("blacklist.errorLoadDetail"));
      }
    },
    [fetcher, t],
  );

  const renderMediaList = (items, kind, parentId) => {
    const list = items || [];
    if (!list.length) {
      return (
        <p style={{ color: COLORS.secondaryText, margin: "0.25rem 0" }}>
          {t("blacklist.modal.attachmentsEmpty")}
        </p>
      );
    }
    return (
      <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.2rem" }}>
        {list.map((media) => (
          <li key={media.id} style={{ marginBottom: "0.35rem" }}>
            <div>
              <strong>{media.filename || t("blacklist.modal.attachmentsTitle")}</strong>{" "}
              <span style={{ color: COLORS.secondaryText }}>{formatBytes(media.size)}</span>
            </div>
            <button
              type="button"
              style={buttonStyle("ghost")}
              onClick={() => handleDownloadMedia(kind, parentId, media)}
            >
              {t("blacklist.modal.attachmentDownload")}
            </button>
          </li>
        ))}
      </ul>
    );
  };

  const columns = useMemo(
    () => [
      {
        key: "name",
        title: t("blacklist.columns.name"),
      },
      {
        key: "phone",
        title: t("blacklist.columns.phone"),
        render: (row) => row.phone || t("common.notAvailable"),
      },
      {
        key: "city",
        title: t("blacklist.columns.city"),
        render: (row) => row.city || t("common.notAvailable"),
      },
      {
        key: "birthdate",
        title: t("blacklist.columns.birthdate"),
        render: (row) => formatBirthdate(row.birthdate),
      },
      {
        key: "is_active",
        title: t("blacklist.columns.isActive"),
        render: (row) => (
          <span style={{ color: row.is_active ? COLORS.success : COLORS.danger, fontWeight: 600 }}>
            {row.is_active ? t("blacklist.status.active") : t("blacklist.status.inactive")}
          </span>
        ),
      },
      {
        key: "complaints_count",
        title: t("blacklist.columns.complaints"),
        render: (row) => row.complaints_count ?? 0,
      },
      {
        key: "appeals_count",
        title: t("blacklist.columns.appeals"),
        render: (row) => row.appeals_count ?? 0,
      },
      {
        key: "date_added",
        title: t("blacklist.columns.added"),
        render: (row) =>
          row.date_added
            ? formatDateTime(row.date_added, language)
            : t("common.notAvailable"),
      },
      {
        key: "actions",
        title: t("blacklist.columns.actions"),
        render: (row) => (
          <button
            type="button"
            style={buttonStyle("ghost")}
            onClick={(event) => {
              event.stopPropagation();
              handleRowClick(row);
            }}
          >
            {t("common.view")}
          </button>
        ),
      },
    ],
    [formatBirthdate, handleRowClick, language, t],
  );

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "1rem",
          flexWrap: "wrap",
          marginBottom: "1.5rem",
        }}
      >
        <div>
          <h2 style={{ margin: 0 }}>{t("blacklist.title")}</h2>
          <p style={{ margin: "0.35rem 0 0", color: COLORS.secondaryText }}>
            {t("blacklist.description")}
          </p>
        </div>
        <button
          type="button"
          style={{
            ...buttonStyle("ghost"),
            opacity: loading ? 0.6 : 1,
            pointerEvents: loading ? "none" : "auto",
          }}
          onClick={handleRefresh}
          disabled={loading}
        >
          {t("blacklist.actions.refresh")}
        </button>
      </div>
      {error ? <Notice kind="error">{error}</Notice> : null}
      {loading ? (
        <Notice kind="info">{t("blacklist.loading")}</Notice>
      ) : (
        <Table
          columns={columns}
          rows={entries}
          emptyText={t("blacklist.empty")}
          rowKey="id"
          onRowClick={handleRowClick}
        />
      )}
      {selectedId ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(15, 23, 42, 0.45)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "1.5rem",
            zIndex: 1100,
          }}
          onClick={handleCloseDetail}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: "1.5rem",
              borderRadius: "14px",
              width: "min(720px, 100%)",
              maxHeight: "90vh",
              overflowY: "auto",
            }}
            onClick={(event) => event.stopPropagation()}
          >
            <h3 style={{ marginTop: 0, marginBottom: "0.75rem" }}>
              {t("blacklist.modal.title", {
                name: entryDetail?.name || t("common.notAvailable"),
              })}
            </h3>
            {detailError ? <Notice kind="error">{detailError}</Notice> : null}
            {detailLoading && !entryDetail ? (
              <Notice kind="info">{t("common.loading")}</Notice>
            ) : null}
            {entryDetail ? (
              <>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                    gap: "0.6rem",
                    marginBottom: "1rem",
                  }}
                >
                  <div>
                    <strong>{t("blacklist.modal.status")}:</strong>{" "}
                    {entryDetail.is_active
                      ? t("blacklist.status.active")
                      : t("blacklist.status.inactive")}
                  </div>
                  <div>
                    <strong>{t("blacklist.modal.city")}:</strong>{" "}
                    {entryDetail.city || t("common.notAvailable")}
                  </div>
                  <div>
                    <strong>{t("blacklist.modal.phone")}:</strong>{" "}
                    {entryDetail.phone || t("common.notAvailable")}
                  </div>
                  <div>
                    <strong>{t("blacklist.modal.birthdate")}:</strong>{" "}
                    {formatBirthdate(entryDetail.birthdate)}
                  </div>
                  <div>
                    <strong>{t("blacklist.columns.complaints")}:</strong>{" "}
                    {entryDetail.complaints_count ??
                      entryDetail.complaints?.length ??
                      0}
                  </div>
                  <div>
                    <strong>{t("blacklist.columns.appeals")}:</strong>{" "}
                    {entryDetail.appeals_count ??
                      entryDetail.appeals?.length ??
                      0}
                  </div>
                  <div>
                    <strong>{t("blacklist.columns.added")}:</strong>{" "}
                    {entryDetail.date_added
                      ? formatDateTime(entryDetail.date_added, language)
                      : t("common.notAvailable")}
                  </div>
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "flex-end",
                    marginBottom: "1rem",
                  }}
                >
                  <button
                    type="button"
                    style={{
                      ...buttonStyle(entryDetail.is_active ? "danger" : "primary"),
                      opacity: updatingStatus ? 0.7 : 1,
                    }}
                    onClick={() =>
                      handleToggleStatus(entryDetail.id, !entryDetail.is_active)
                    }
                    disabled={updatingStatus}
                  >
                    {updatingStatus
                      ? t("common.loading")
                      : entryDetail.is_active
                        ? t("blacklist.actions.deactivate")
                        : t("blacklist.actions.activate")}
                  </button>
                </div>
                <section style={{ marginBottom: "1.25rem" }}>
                  <h4 style={{ margin: "0 0 0.5rem" }}>
                    {t("blacklist.modal.complaintsTitle")}
                  </h4>
                  {(entryDetail.complaints || []).length ? (
                    <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
                      {entryDetail.complaints.map((complaint) => (
                        <li key={complaint.id} style={{ marginBottom: "0.6rem" }}>
                          <strong>
                            {t("blacklist.modal.complaintHeader", {
                              date: formatDateTime(
                                complaint.complaint_date,
                                language,
                              ),
                              author: complaint.added_by,
                            })}
                          </strong>
                          <div style={{ color: COLORS.secondaryText }}>
                            {complaint.reason}
                          </div>
                          <div style={{ marginTop: "0.35rem" }}>
                            <em>{t("blacklist.modal.attachmentsTitle")}:</em>
                            {renderMediaList(complaint.media, "complaint", complaint.id)}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p style={{ color: COLORS.secondaryText }}>
                      {t("blacklist.modal.complaintsEmpty")}
                    </p>
                  )}
                </section>
                <section style={{ marginBottom: "1.25rem" }}>
                  <h4 style={{ margin: "0 0 0.5rem" }}>
                    {t("blacklist.modal.appealsTitle")}
                  </h4>
                  {(entryDetail.appeals || []).length ? (
                    <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
                      {entryDetail.appeals.map((appeal) => (
                        <li key={appeal.id} style={{ marginBottom: "0.6rem" }}>
                          <strong>
                            {t("blacklist.modal.appealHeader", {
                              date: formatDateTime(appeal.appeal_date, language),
                              author: appeal.appeal_by,
                            })}
                          </strong>
                          <div style={{ color: COLORS.secondaryText }}>
                            {appeal.reason}
                          </div>
                          <div style={{ marginTop: "0.35rem" }}>
                            <em>{t("blacklist.modal.attachmentsTitle")}:</em>
                            {renderMediaList(appeal.media, "appeal", appeal.id)}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p style={{ color: COLORS.secondaryText }}>
                      {t("blacklist.modal.appealsEmpty")}
                    </p>
                  )}
                </section>
              </>
            ) : null}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
              <button
                type="button"
                style={buttonStyle("ghost")}
                onClick={handleCloseDetail}
              >
                {t("blacklist.modal.close")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
};

const RolesTab = ({ fetcher, profile }) => {
  const { t } = useI18n();
  const [roles, setRoles] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createSuccess, setCreateSuccess] = useState("");
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newTelegram, setNewTelegram] = useState("");
  const [newRole, setNewRole] = useState("");
  const manageRoles = (profile?.roles || []).some((r) => ["owner", "superadmin"].includes(r));

  const roleLabel = useCallback(
    (roleOrSlug) => {
      const slug = typeof roleOrSlug === "string" ? roleOrSlug : roleOrSlug?.slug;
      if (!slug) {
        return "";
      }
      const translated = t(`roles.labels.${slug}`);
      if (translated && translated !== `roles.labels.${slug}`) {
        return translated;
      }
      if (typeof roleOrSlug === "object" && roleOrSlug?.title) {
        return roleOrSlug.title;
      }
      return slug;
    },
    [t],
  );

  const canAssignRole = useCallback(
    (roleSlug) => {
      if ((profile?.roles || []).includes("owner")) return true;
      if ((profile?.roles || []).includes("superadmin")) {
        return !["owner", "superadmin"].includes(roleSlug);
      }
      return false;
    },
    [profile],
  );

  const loadData = useCallback(async () => {
    if (!manageRoles) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [rolesResp, accountsResp] = await Promise.all([
        fetcher("/admin/roles"),
        fetcher("/admin/admin-accounts"),
      ]);
      const rolesData = await rolesResp.json();
      const accountsData = await accountsResp.json();
      setRoles(rolesData);
      setAccounts(accountsData);
      setError("");
    } catch (err) {
      setError(err.message || t("roles.error"));
    } finally {
      setLoading(false);
    }
  }, [fetcher, manageRoles, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAssign = useCallback(
    async (accountId, role) => {
      try {
        await fetcher(`/admin/roles/${role.id}/assign`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify([String(accountId)]),
        });
        await loadData();
      } catch (err) {
        setError(err.message || t("roles.error"));
      }
    },
    [fetcher, loadData, t],
  );

  const handleRevoke = useCallback(
    async (accountId, role) => {
      try {
        await fetcher(`/admin/roles/${role.id}/revoke`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify([String(accountId)]),
        });
        await loadData();
      } catch (err) {
        setError(err.message || t("roles.error"));
      }
    },
    [fetcher, loadData, t],
  );

  const handleCreate = useCallback(
    async (event) => {
      event?.preventDefault();
      setCreateError("");
      setCreateSuccess("");
      if (!newUsername.trim() || !newPassword.trim()) {
        setCreateError(t("roles.createError"));
        return;
      }
      setCreating(true);
      try {
        const payload = {
          username: newUsername.trim(),
          password: newPassword,
        };
        const tg = (newTelegram || "").trim();
        if (tg) {
          const parsed = parseInt(tg, 10);
          if (!Number.isNaN(parsed)) {
            payload.telegram_id = parsed;
          }
        }
        if (newRole) {
          payload.roles = [newRole];
        }
        const resp = await fetcher("/admin/admin-accounts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await resp.json();
        setAccounts((prev) => [...prev, data]);
        setNewUsername("");
        setNewPassword("");
        setNewTelegram("");
        setNewRole("");
        setCreateSuccess(t("roles.created"));
      } catch (err) {
        setCreateError(err.message || t("roles.createError"));
      } finally {
        setCreating(false);
      }
    },
    [fetcher, newPassword, newRole, newTelegram, newUsername, t],
  );

  if (!manageRoles) {
    return <Notice kind="warning">{t("roles.notAllowed")}</Notice>;
  }

  if (loading) {
    return <Notice kind="info">{t("roles.loading")}</Notice>;
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "1.5rem" }}>
      <div
        style={{
          padding: "1rem",
          border: `1px solid ${COLORS.border}`,
          borderRadius: "12px",
          backgroundColor: "#f8fafc",
        }}
      >
        <h3 style={{ marginTop: 0 }}>{t("roles.rolesTitle")}</h3>
        {roles.length ? (
          <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {roles.map((role) => (
              <li key={role.id}>
                <strong>{role.slug}</strong> — {roleLabel(role)}
              </li>
            ))}
          </ul>
        ) : (
          <p style={{ color: COLORS.secondaryText }}>{t("roles.emptyRoles")}</p>
        )}
      </div>
      <div>
        <h3 style={{ marginTop: 0 }}>{t("roles.accountsTitle")}</h3>
        <form
          onSubmit={handleCreate}
          style={{
            marginBottom: "1rem",
            padding: "1rem",
            border: `1px solid ${COLORS.border}`,
            borderRadius: "12px",
            backgroundColor: "#f8fafc",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "0.75rem",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            <label style={{ fontWeight: 600 }}>{t("roles.username")}</label>
            <input
              type="text"
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              placeholder="admin"
              style={{ padding: "0.55rem", borderRadius: "8px", border: `1px solid ${COLORS.border}` }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            <label style={{ fontWeight: 600 }}>{t("roles.password")}</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="********"
              style={{ padding: "0.55rem", borderRadius: "8px", border: `1px solid ${COLORS.border}` }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            <label style={{ fontWeight: 600 }}>{t("roles.telegram")}</label>
            <input
              type="text"
              value={newTelegram}
              onChange={(e) => setNewTelegram(e.target.value)}
              placeholder="123456789"
              style={{ padding: "0.55rem", borderRadius: "8px", border: `1px solid ${COLORS.border}` }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            <label style={{ fontWeight: 600 }}>{t("roles.rolePick")}</label>
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              style={{ padding: "0.55rem", borderRadius: "8px", border: `1px solid ${COLORS.border}` }}
            >
              <option value="">{t("roles.rolePlaceholder")}</option>
              {roles.map((role) => (
                <option key={role.id} value={role.slug} disabled={!canAssignRole(role.slug)}>
                  {role.slug} — {roleLabel(role)}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button type="submit" style={buttonStyle("primary")} disabled={creating}>
              {creating ? t("roles.creating") : t("roles.create")}
            </button>
          </div>
          {createError ? <Notice kind="error">{createError}</Notice> : null}
          {createSuccess ? <Notice kind="success">{createSuccess}</Notice> : null}
        </form>
        {error ? <Notice kind="error">{error}</Notice> : null}
        {!accounts.length ? (
          <p style={{ color: COLORS.secondaryText }}>{t("roles.emptyAccounts")}</p>
        ) : (
          <Table
            columns={[
              { key: "username", title: t("roles.account") },
              {
                key: "telegram_id",
                title: t("roles.telegram"),
                render: (row) => row.telegram_id || t("common.notAvailable"),
              },
              {
                key: "is_active",
                title: t("roles.status"),
                render: (row) => (row.is_active ? t("common.yes") : t("common.no")),
              },
              {
                key: "roles",
                title: t("roles.roleList"),
                render: (row) =>
                  (row.roles || []).length
                    ? row.roles.map((slug) => roleLabel(slug)).join(", ")
                    : t("common.notAvailable"),
              },
              {
                key: "actions",
                title: t("roles.actions"),
                render: (row) => (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                    {roles.map((role) => {
                      const hasRole = (row.roles || []).includes(role.slug);
                      const allowed = canAssignRole(role.slug);
                      if (!allowed && role.slug !== "owner") {
                        return null;
                      }
                      return hasRole ? (
                        <button
                          key={`${row.id}-${role.id}-revoke`}
                          type="button"
                          style={buttonStyle("ghost")}
                          onClick={() => handleRevoke(row.id, role)}
                          disabled={!allowed}
                          title={!allowed ? t("roles.ownerOnly") : undefined}
                        >
                          {t("roles.revoke")} {roleLabel(role)}
                        </button>
                      ) : (
                        <button
                          key={`${row.id}-${role.id}-assign`}
                          type="button"
                          style={buttonStyle("primary")}
                          onClick={() => handleAssign(row.id, role)}
                          disabled={!allowed}
                          title={!allowed ? t("roles.ownerOnly") : undefined}
                        >
                          {t("roles.assign")} {roleLabel(role)}
                        </button>
                      );
                    })}
                    <button
                      type="button"
                      style={buttonStyle("danger")}
                      onClick={async () => {
                        if (!confirm(`Delete admin ${row.username}?`)) return;
                        try {
                          const resp = await fetcher(`/admin/admin-accounts/${row.id}`, { method: "DELETE" });
                          if (!resp.ok) {
                            const text = await resp.text();
                            throw new Error(text || "Failed");
                          }
                          await loadData();
                        } catch (err) {
                          setError(err.message || t("roles.error"));
                        }
                      }}
                    >
                      {t("common.delete")}
                    </button>
                  </div>
                ),
              },
            ]}
            rows={accounts}
            emptyText={t("roles.emptyAccounts")}
            rowKey="id"
          />
        )}
      </div>
    </div>
  );
};

const UserManagementTab = ({ fetcher, profile }) => {
  const { t } = useI18n();
  const [subTab, setSubTab] = useState("users");
  const [roleOptions, setRoleOptions] = useState([]);
  const manageRoles = (profile?.roles || []).some((r) => ["owner", "superadmin"].includes(r));

  useEffect(() => {
    const loadRoles = async () => {
      if (!manageRoles) return;
      try {
        const resp = await fetcher("/admin/roles");
        const data = await resp.json();
        setRoleOptions(data || []);
      } catch (err) {
        // ignore, RolesTab will still fetch on its own
      }
    };
    loadRoles();
  }, [fetcher, manageRoles]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {[
          { key: "users", label: t("tabs.users") },
          { key: "roles", label: t("tabs.roles") },
        ].map((tab) => (
          <button
            key={tab.key}
            type="button"
            style={subTab === tab.key ? buttonStyle("primary") : buttonStyle("ghost")}
            onClick={() => setSubTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {subTab === "users" ? (
        <UsersTab fetcher={fetcher} roles={profile?.roles} roleOptions={roleOptions} />
      ) : (
        <RolesTab fetcher={fetcher} profile={profile} />
      )}
    </div>
  );
};

const DocumentsTab = ({ fetcher }) => (
  <DocumentManager
    fetcher={fetcher}
    config={{
      translationBase: "documents",
      treeEndpoint: "/admin/document-tree",
      itemListKey: "topics",
    }}
  />
);

const ContractTemplatesTab = ({ fetcher }) => (
  <DocumentManager
    fetcher={fetcher}
    config={{
      translationBase: "contractTemplates",
      treeEndpoint: "/admin/contract-templates/tree",
      itemListKey: "templates",
    }}
  />
);

const CourtCaseEditor = ({
  t,
  caseData,
  canManage,
  statusDraft,
  setStatusDraft,
  onStatusSubmit,
  scholarNameDraft,
  setScholarNameDraft,
  scholarContactDraft,
  setScholarContactDraft,
  scholarIdDraft,
  setScholarIdDraft,
  scholars,
  selectedScholarId,
  setSelectedScholarId,
  onSubmit,
}) => {
  const handleSelectScholar = (value) => {
    setSelectedScholarId(value);
    const scholarId = Number(value || 0);
    const scholar = (scholars || []).find((item) => item.id === scholarId);
    if (scholar) {
      setScholarNameDraft(scholar.username || "");
      setScholarIdDraft(String(scholar.id));
      setScholarContactDraft(
        scholar.telegram_id ? String(scholar.telegram_id) : "",
      );
    }
  };

  return (
    <div
      style={{
        padding: "0.75rem",
        border: `1px solid ${COLORS.border}`,
        borderRadius: "10px",
        backgroundColor: "#fef9c3",
        display: "grid",
        gap: "0.6rem",
        marginBottom: "1rem",
      }}
    >
      <strong>{t("courts.admin.title")}</strong>
      {caseData ? (
        <>
          <div>
            <strong>{t("courts.admin.caseNumber")}:</strong>{" "}
            {caseData.case_number || caseData.id || t("common.notAvailable")}
          </div>
          <div>
            <strong>{t("courts.admin.category")}:</strong>{" "}
            {resolveCourtCategoryLabel(t, caseData.category)}
          </div>
          <div>
            <strong>{t("courts.admin.plaintiff")}:</strong>{" "}
            {caseData.plaintiff || t("common.notAvailable")}
          </div>
          <div>
            <strong>{t("courts.admin.defendant")}:</strong>{" "}
            {caseData.defendant || t("common.notAvailable")}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
            <span>{t("tasks.statusCase")}</span>
            <select
              value={statusDraft || caseData?.status || ""}
              onChange={(e) => setStatusDraft(e.target.value)}
              style={{ padding: "0.35rem", borderRadius: "8px" }}
              disabled={!canManage}
            >
              {["open", "in_progress", "closed", "cancelled"].map((s) => (
                <option key={s} value={s}>
                  {resolveCourtStatusLabel(t, s)}
                </option>
              ))}
            </select>
            <button
              type="button"
              style={buttonStyle("ghost")}
              onClick={onStatusSubmit}
              disabled={!canManage}
            >
              {t("courts.admin.statusUpdate")}
            </button>
          </div>
          <label style={{ display: "grid", gap: "0.3rem" }}>
            <span>{t("courts.admin.scholarSelect")}</span>
            <select
              value={selectedScholarId}
              onChange={(e) => handleSelectScholar(e.target.value)}
              style={{ padding: "0.4rem", borderRadius: "8px" }}
              disabled={!canManage || !(scholars || []).length}
            >
              <option value="">{t("courts.admin.scholarSelectPlaceholder")}</option>
              {(scholars || []).map((scholar) => (
                <option key={scholar.id} value={String(scholar.id)}>
                  {scholar.username}
                </option>
              ))}
            </select>
            {!(scholars || []).length ? (
              <span style={{ color: COLORS.secondaryText, fontSize: "0.85rem" }}>
                {t("courts.admin.scholarEmpty")}
              </span>
            ) : null}
          </label>
          <label style={{ display: "grid", gap: "0.3rem" }}>
            <span>{t("courts.admin.scholarName")}</span>
            <input
              type="text"
              value={scholarNameDraft}
              onChange={(e) => setScholarNameDraft(e.target.value)}
              style={{ padding: "0.45rem", borderRadius: "8px" }}
              disabled={!canManage}
            />
          </label>
          <label style={{ display: "grid", gap: "0.3rem" }}>
            <span>{t("courts.admin.scholarContact")}</span>
            <input
              type="text"
              value={scholarContactDraft}
              onChange={(e) => setScholarContactDraft(e.target.value)}
              style={{ padding: "0.45rem", borderRadius: "8px" }}
              disabled={!canManage}
            />
          </label>
          <label style={{ display: "grid", gap: "0.3rem" }}>
            <span>{t("courts.admin.scholarId")}</span>
            <input
              type="text"
              value={scholarIdDraft}
              onChange={(e) => setScholarIdDraft(e.target.value)}
              style={{ padding: "0.45rem", borderRadius: "8px" }}
              disabled={!canManage}
            />
          </label>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              style={buttonStyle("primary")}
              onClick={onSubmit}
              disabled={!canManage}
            >
              {t("courts.admin.update")}
            </button>
          </div>
          <div style={{ color: COLORS.secondaryText, fontSize: "0.85rem" }}>
            {t("courts.admin.statusHint")}
          </div>
        </>
      ) : (
        <div style={{ color: COLORS.secondaryText }}>{t("common.loading")}</div>
      )}
    </div>
  );
};

const TasksTab = ({ fetcher, profile }) => {
  const { t, language } = useI18n();
  const roleSet = useMemo(() => new Set(profile?.roles || []), [profile?.roles]);
  const canManage =
    roleSet.has("owner") ||
    roleSet.has("superadmin") ||
    roleSet.has("admin_work_items_manage");

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [specs, setSpecs] = useState([]);

  const [topic, setTopic] = useState("");
  const [mine, setMine] = useState(false);
  const [unassigned, setUnassigned] = useState(false);
  const [statusCsv, setStatusCsv] = useState(
    "new,assigned,in_progress,waiting_user,waiting_scholar",
  );

  const [selectedId, setSelectedId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [events, setEvents] = useState([]);
  const [specContent, setSpecContent] = useState("");
  const [specOpen, setSpecOpen] = useState(false);
  const [statusDraft, setStatusDraft] = useState("");
  const [commentDraft, setCommentDraft] = useState("");
  const [messageDraft, setMessageDraft] = useState("");
  const [courtCase, setCourtCase] = useState(null);
  const [caseStatusDraft, setCaseStatusDraft] = useState("");
  const [contractData, setContractData] = useState(null);
  const [contractStatusDraft, setContractStatusDraft] = useState("");
  const [scholarNameDraft, setScholarNameDraft] = useState("");
  const [scholarContactDraft, setScholarContactDraft] = useState("");
  const [scholarIdDraft, setScholarIdDraft] = useState("");
  const [scholars, setScholars] = useState([]);
  const [selectedScholarId, setSelectedScholarId] = useState("");

  const topicLabel = useCallback(
    (value) => {
      const found = (specs || []).find((s) => s.key === value);
      return found?.title || value || t("common.notAvailable");
    },
    [specs, t],
  );

  const loadSpecs = useCallback(async () => {
    try {
      const response = await fetcher("/admin/specs");
      const data = await response.json();
      setSpecs(Array.isArray(data) ? data : []);
    } catch (_err) {
      setSpecs([]);
    }
  }, [fetcher]);

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (topic) params.set("topic", topic);
      if (statusCsv) params.set("status", statusCsv);
      if (mine) params.set("mine", "true");
      if (unassigned) params.set("unassigned", "true");
      const response = await fetcher(`/admin/work-items?${params.toString()}`);
      const data = await response.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || t("tasks.errorLoad"));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [fetcher, mine, statusCsv, t, topic, unassigned]);

  const loadCourtCase = useCallback(
    async (caseId) => {
      if (!caseId) {
        setCourtCase(null);
        return;
      }
      try {
        const response = await fetcher(`/admin/court-cases/${caseId}`);
        const data = await response.json();
        setCourtCase(data || null);
        setCaseStatusDraft(data?.status || "");
        setScholarNameDraft(data?.scholar_name || "");
        setScholarContactDraft(data?.scholar_contact || "");
        setScholarIdDraft(data?.scholar_id || "");
        if (data?.scholar_id && String(Number(data.scholar_id)) === String(data.scholar_id)) {
          setSelectedScholarId(String(Number(data.scholar_id)));
        } else {
          setSelectedScholarId("");
        }
      } catch (err) {
        setCourtCase(null);
        setError(err.message || t("errors.requestFailed"));
      }
    },
    [fetcher, t],
  );

  const loadContract = useCallback(
    async (contractId) => {
      if (!contractId) {
        setContractData(null);
        return;
      }
      setError("");
      try {
        const response = await fetcher(`/admin/contracts/${contractId}`);
        const data = await response.json();
        setContractData(data || null);
        setContractStatusDraft(data?.status || "");
        setScholarNameDraft(data?.scholar_name || "");
        setScholarContactDraft(data?.scholar_contact || "");
        setScholarIdDraft(data?.scholar_id || "");
        if (data?.scholar_id && String(Number(data.scholar_id)) === String(data.scholar_id)) {
          setSelectedScholarId(String(Number(data.scholar_id)));
        } else {
          setSelectedScholarId("");
        }
      } catch (err) {
        setContractData(null);
        setError(err.message || t("errors.requestFailed"));
      }
    },
    [fetcher, t],
  );

  const loadScholars = useCallback(async () => {
    try {
      const response = await fetcher("/admin/scholars");
      const data = await response.json();
      setScholars(Array.isArray(data) ? data : []);
    } catch (_err) {
      setScholars([]);
    }
  }, [fetcher]);


  const loadSelected = useCallback(
    async (workItemId) => {
      if (!workItemId) return;
      setError("");
      try {
        const [detailResp, eventsResp] = await Promise.all([
          fetcher(`/admin/work-items/${workItemId}`),
          fetcher(`/admin/work-items/${workItemId}/events`),
        ]);
        const detail = await detailResp.json();
        const ev = await eventsResp.json();
        setSelected(detail);
        setEvents(Array.isArray(ev) ? ev : []);
        setStatusDraft(detail?.status || "");
        if (detail?.topic === "courts" && detail?.payload?.case_id) {
          await loadCourtCase(detail.payload.case_id);
        } else {
          setCourtCase(null);
        }
        if (detail?.topic === "contracts" && detail?.payload?.contract_id) {
          await loadContract(detail.payload.contract_id);
        } else {
          setContractData(null);
        }
      } catch (err) {
        setError(err.message || t("tasks.errorLoad"));
      }
    },
    [fetcher, loadContract, loadCourtCase, t],
  );

  useEffect(() => {
    loadSpecs();
  }, [loadSpecs]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  useEffect(() => {
    loadScholars();
  }, [loadScholars]);

  useEffect(() => {
    if (!selectedId) return;
    loadSelected(selectedId);
  }, [loadSelected, selectedId]);

  const handleTake = async () => {
    if (!selectedId) return;
    setError("");
    try {
      await fetcher(`/admin/work-items/${selectedId}/assign`, { method: "POST" });
      await Promise.all([loadSelected(selectedId), loadItems()]);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleUpdateStatus = async () => {
    if (!selectedId) return;
    const nextStatus = statusDraft || selected?.status || "";
    if (!nextStatus) return;
    setError("");
    setStatusUpdating(true);
    try {
      await fetcher(`/admin/work-items/${selectedId}/status`, {
        method: "POST",
        body: JSON.stringify({ status: String(nextStatus) }),
      });
      setSelected((prev) => (prev ? { ...prev, status: nextStatus } : prev));
      setItems((prev) =>
        prev.map((item) =>
          item.id === selectedId ? { ...item, status: nextStatus } : item,
        ),
      );
      setStatusDraft(nextStatus);
      await Promise.all([loadSelected(selectedId), loadItems()]);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    } finally {
      setStatusUpdating(false);
    }
  };

  const handleUpdateCourtCase = async () => {
    if (!courtCase?.id) return;
    const nextStatus = caseStatusDraft || courtCase?.status || "";
    const hasUpdate =
      nextStatus ||
      scholarNameDraft !== "" ||
      scholarContactDraft !== "" ||
      scholarIdDraft !== "";
    if (!hasUpdate) return;
    setError("");
    try {
      const response = await fetcher(`/admin/court-cases/${courtCase.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: nextStatus || undefined,
          scholar_name: scholarNameDraft,
          scholar_contact: scholarContactDraft,
          scholar_id: scholarIdDraft,
        }),
      });
      const updated = await response.json();
      setCourtCase(updated || null);
      setCaseStatusDraft(updated?.status || "");
      setScholarNameDraft(updated?.scholar_name || "");
      setScholarContactDraft(updated?.scholar_contact || "");
      setScholarIdDraft(updated?.scholar_id || "");
      if (updated?.scholar_id && String(Number(updated.scholar_id)) === String(updated.scholar_id)) {
        setSelectedScholarId(String(Number(updated.scholar_id)));
      } else {
        setSelectedScholarId("");
      }
      await Promise.all([loadSelected(selectedId), loadItems()]);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleUpdateCourtCaseStatus = async () => {
    if (!courtCase?.id) return;
    const nextStatus = caseStatusDraft || courtCase?.status || "";
    if (!nextStatus) return;
    setError("");
    try {
      const response = await fetcher(`/admin/court-cases/${courtCase.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: String(nextStatus) }),
      });
      const updated = await response.json();
      setCourtCase(updated || null);
      setCaseStatusDraft(updated?.status || "");
      await Promise.all([loadSelected(selectedId), loadItems()]);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleUpdateContract = async () => {
    if (!contractData?.id) return;
    const nextStatus = contractStatusDraft || contractData?.status || "";
    const hasUpdate =
      nextStatus ||
      scholarNameDraft !== "" ||
      scholarContactDraft !== "" ||
      scholarIdDraft !== "";
    if (!hasUpdate) return;
    setError("");
    try {
      const response = await fetcher(`/admin/contracts/${contractData.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: nextStatus || undefined,
          scholar_name: scholarNameDraft,
          scholar_contact: scholarContactDraft,
          scholar_id: scholarIdDraft,
        }),
      });
      const updated = await response.json();
      setContractData(updated || null);
      setContractStatusDraft(updated?.status || "");
      setScholarNameDraft(updated?.scholar_name || "");
      setScholarContactDraft(updated?.scholar_contact || "");
      setScholarIdDraft(updated?.scholar_id || "");
      if (updated?.scholar_id && String(Number(updated.scholar_id)) === String(updated.scholar_id)) {
        setSelectedScholarId(String(Number(updated.scholar_id)));
      } else {
        setSelectedScholarId("");
      }
      await Promise.all([loadSelected(selectedId), loadItems()]);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleUpdateContractStatus = async () => {
    if (!contractData?.id) return;
    const nextStatus = contractStatusDraft || contractData?.status || "";
    if (!nextStatus) return;
    setError("");
    try {
      const response = await fetcher(`/admin/contracts/${contractData.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: String(nextStatus) }),
      });
      const updated = await response.json();
      setContractData(updated || null);
      setContractStatusDraft(updated?.status || "");
      await Promise.all([loadSelected(selectedId), loadItems()]);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleAddComment = async () => {
    if (!selectedId || !commentDraft.trim()) return;
    setError("");
    try {
      await fetcher(`/admin/work-items/${selectedId}/comment`, {
        method: "POST",
        body: JSON.stringify({ message: commentDraft.trim() }),
      });
      setCommentDraft("");
      await loadSelected(selectedId);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleNotifyUser = async () => {
    if (!selectedId || !messageDraft.trim()) return;
    setError("");
    try {
      await fetcher(`/admin/work-items/${selectedId}/notify-user`, {
        method: "POST",
        body: JSON.stringify({ text: messageDraft.trim() }),
      });
      setMessageDraft("");
      await loadSelected(selectedId);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleOpenSpec = async () => {
    const key = selected?.topic || topic;
    if (!key) return;
    setError("");
    try {
      const response = await fetcher(`/admin/specs/${encodeURIComponent(key)}`);
      const data = await response.json();
      setSpecContent(String(data?.content || ""));
      setSpecOpen(true);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const columns = [
    { key: "id", title: t("tasks.id"), width: "90px" },
    { key: "topic", title: t("tasks.topic"), render: (row) => topicLabel(row.topic) },
    {
      key: "kind",
      title: t("tasks.kind"),
      width: "200px",
      render: (row) => resolveTaskKindLabel(t, row.kind),
    },
    {
      key: "status",
      title: t("tasks.status"),
      width: "140px",
      render: (row) => resolveTaskStatusLabel(t, row.status),
    },
    {
      key: "priority",
      title: t("tasks.priority"),
      width: "110px",
      render: (row) => row.priority ?? t("common.notAvailable"),
    },
    {
      key: "created_at",
      title: t("tasks.created"),
      width: "210px",
      render: (row) =>
        row.created_at
          ? formatDateTime(row.created_at, language)
          : t("common.notAvailable"),
    },
  ];

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {error ? <Notice kind="error">{error}</Notice> : null}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "0.75rem",
          padding: "0.75rem",
          border: `1px solid ${COLORS.border}`,
          borderRadius: "12px",
          backgroundColor: "#f8fafc",
        }}
      >
        <strong style={{ marginRight: "0.5rem" }}>{t("tasks.title")}</strong>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("tasks.topic")}
          <select
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            style={{ padding: "0.4rem", borderRadius: "8px" }}
          >
            <option value="">{t("tasks.allTopics")}</option>
            {(specs || []).map((s) => (
              <option key={s.key} value={s.key}>
                {s.title}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("tasks.status")}
          <input
            type="text"
            value={statusCsv}
            onChange={(e) => setStatusCsv(e.target.value)}
            placeholder="new,assigned,in_progress"
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "260px" }}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />
          {t("tasks.mine")}
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <input
            type="checkbox"
            checked={unassigned}
            onChange={(e) => setUnassigned(e.target.checked)}
          />
          {t("tasks.unassigned")}
        </label>
        <button type="button" style={buttonStyle("ghost")} onClick={loadItems} disabled={loading}>
          {t("tasks.refresh")}
        </button>
      </div>
      {loading ? <div>{t("common.loading")}</div> : null}
      <Table
        columns={columns}
        rows={items}
        emptyText={t("tasks.empty")}
        rowKey="id"
        onRowClick={(row) => {
          setSelectedId(row.id);
          setSelected(null);
          setEvents([]);
          setCommentDraft("");
          setMessageDraft("");
            setSpecOpen(false);
            setSpecContent("");
            setCourtCase(null);
            setCaseStatusDraft("");
            setContractData(null);
            setContractStatusDraft("");
            setScholarNameDraft("");
            setScholarContactDraft("");
            setScholarIdDraft("");
        }}
      />

      {selectedId ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setSelectedId(null)}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: "1.25rem 1.5rem",
              borderRadius: "12px",
              minWidth: "420px",
              maxWidth: "980px",
              width: "92vw",
              maxHeight: "92vh",
              overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>
                {t("tasks.details")} ? {selectedId}
              </h3>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button type="button" style={buttonStyle("ghost")} onClick={handleOpenSpec}>
                  {t("tasks.viewSpec")}
                </button>
                <button type="button" style={buttonStyle("ghost")} onClick={() => setSelectedId(null)}>
                  {t("tasks.close")}
                </button>
              </div>
            </div>

            {selected ? (
              <div style={{ display: "grid", gap: "0.5rem", color: COLORS.secondaryText, marginBottom: "1rem" }}>
                <div>
                  <strong>{t("tasks.topic")}: </strong> {topicLabel(selected.topic)}
                </div>
                <div>
                  <strong>{t("tasks.kind")}: </strong> {resolveTaskKindLabel(t, selected.kind)}
                </div>
                <div>
                  <strong>{t("tasks.status")}: </strong> {resolveTaskStatusLabel(t, selected.status)}
                </div>
                <div>
                  <strong>{t("tasks.priority")}: </strong> {selected.priority ?? t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("tasks.targetUser")}: </strong> {selected.target_user_id ?? t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("tasks.created")}: </strong> {selected.created_at ? formatDateTime(selected.created_at, language) : t("common.notAvailable")}
                </div>
              </div>
            ) : (
              <div style={{ marginBottom: "1rem", color: COLORS.secondaryText }}>{t("common.loading")}</div>
            )}

            {specOpen ? (
              <div style={{ marginBottom: "1rem" }}>
                <h4 style={{ margin: "0 0 0.5rem" }}>{t("tasks.viewSpec")}</h4>
                <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: "0.92rem" }}>
                  {specContent || t("common.notAvailable")}
                </pre>
              </div>
            ) : null}

            {selected?.topic === "courts" ? (
              <CourtCaseEditor
                t={t}
                caseData={courtCase}
                canManage={canManage}
                statusDraft={caseStatusDraft}
                setStatusDraft={setCaseStatusDraft}
                onStatusSubmit={handleUpdateCourtCaseStatus}
                scholarNameDraft={scholarNameDraft}
                setScholarNameDraft={setScholarNameDraft}
                scholarContactDraft={scholarContactDraft}
                setScholarContactDraft={setScholarContactDraft}
                scholarIdDraft={scholarIdDraft}
                setScholarIdDraft={setScholarIdDraft}
                scholars={scholars}
                selectedScholarId={selectedScholarId}
                setSelectedScholarId={setSelectedScholarId}
                onSubmit={handleUpdateCourtCase}
              />
            ) : null}
            {selected?.topic === "contracts" ? (
              <ContractEditor
                t={t}
                contractData={contractData}
                canManage={canManage}
                statusDraft={contractStatusDraft}
                setStatusDraft={setContractStatusDraft}
                onStatusSubmit={handleUpdateContractStatus}
                scholarNameDraft={scholarNameDraft}
                setScholarNameDraft={setScholarNameDraft}
                scholarContactDraft={scholarContactDraft}
                setScholarContactDraft={setScholarContactDraft}
                scholarIdDraft={scholarIdDraft}
                setScholarIdDraft={setScholarIdDraft}
                scholars={scholars}
                selectedScholarId={selectedScholarId}
                setSelectedScholarId={setSelectedScholarId}
                onSubmit={handleUpdateContract}
              />
            ) : null}

            {canManage ? (
              <div
                style={{
                  padding: "0.75rem",
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: "10px",
                  backgroundColor: "#f8fafc",
                  display: "grid",
                  gap: "0.75rem",
                  marginBottom: "1rem",
                }}
              >
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                  <button type="button" style={buttonStyle("primary")} onClick={handleTake}>
                    {t("tasks.take")}
                  </button>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    {selected?.topic === "courts" ? t("tasks.statusTask") : t("tasks.status")}
                    <select
                      value={statusDraft || selected?.status || ""}
                      onChange={(e) => setStatusDraft(e.target.value)}
                      style={{ padding: "0.35rem", borderRadius: "8px" }}
                    >
                      {[
                        "new",
                        "assigned",
                        "in_progress",
                        "waiting_user",
                        "waiting_scholar",
                        "done",
                        "canceled",
                      ].map((s) => (
                        <option key={s} value={s}>{resolveTaskStatusLabel(t, s)}</option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    style={buttonStyle("ghost")}
                    onClick={handleUpdateStatus}
                    disabled={statusUpdating}
                  >
                    {t("tasks.updateStatus")}
                  </button>
                </div>

                <div style={{ display: "grid", gap: "0.4rem" }}>
                  <strong>{t("tasks.comment")}</strong>
                  <textarea
                    value={commentDraft}
                    onChange={(e) => setCommentDraft(e.target.value)}
                    rows={3}
                    style={{ padding: "0.6rem", borderRadius: "10px", border: `1px solid ${COLORS.border}` }}
                  />
                  <button type="button" style={buttonStyle("ghost")} onClick={handleAddComment}>
                    {t("tasks.addComment")}
                  </button>
                </div>

                <div style={{ display: "grid", gap: "0.4rem" }}>
                  <strong>{t("tasks.notify")}</strong>
                  <textarea
                    value={messageDraft}
                    onChange={(e) => setMessageDraft(e.target.value)}
                    rows={3}
                    style={{ padding: "0.6rem", borderRadius: "10px", border: `1px solid ${COLORS.border}` }}
                  />
                  <button type="button" style={buttonStyle("primary")} onClick={handleNotifyUser}>
                    {t("tasks.send")}
                  </button>
                </div>
              </div>
            ) : null}

            <div style={{ display: "grid", gap: "0.5rem" }}>
              <h4 style={{ margin: 0 }}>{t("tasks.events")}</h4>
              {(events || []).length ? (
                <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
                  {events.map((ev) => (
                    <li key={ev.id} style={{ marginBottom: "0.6rem" }}>
                      <strong>{ev.event_type}</strong>{" "}
                      <span style={{ color: COLORS.secondaryText }}>
                        ({ev.created_at ? formatDateTime(ev.created_at, language) : t("common.notAvailable")})
                      </span>
                      {ev.message ? (
                        <div style={{ color: COLORS.secondaryText, whiteSpace: "pre-wrap" }}>{ev.message}</div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <div style={{ color: COLORS.secondaryText }}>{t("common.notAvailable")}</div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

const CourtCasesTab = ({ fetcher, profile }) => {
  const { t, language } = useI18n();
  const roleSet = useMemo(() => new Set(profile?.roles || []), [profile?.roles]);
  const canManage =
    roleSet.has("owner") ||
    roleSet.has("superadmin") ||
    roleSet.has("admin_work_items_manage");
  const canAssignAny = roleSet.has("owner") || roleSet.has("superadmin");
  const statusLabel = useCallback(
    (value) => {
      if (!value) return t("common.notAvailable");
      const key = `courts.status.${value}`;
      const label = t(key);
      return label === key ? value : label;
    },
    [t],
  );
  const categoryLabel = useCallback(
    (value) => {
      if (!value) return t("common.notAvailable");
      const key = `courts.category.${value}`;
      const label = t(key);
      return label === key ? value : label;
    },
    [t],
  );

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusCsv, setStatusCsv] = useState("");
  const [selected, setSelected] = useState(null);
  const [caseStatusDraft, setCaseStatusDraft] = useState("");
  const [scholarNameDraft, setScholarNameDraft] = useState("");
  const [scholarContactDraft, setScholarContactDraft] = useState("");
  const [scholarIdDraft, setScholarIdDraft] = useState("");
  const [scholars, setScholars] = useState([]);
  const [selectedScholarId, setSelectedScholarId] = useState("");
  const [adminAccounts, setAdminAccounts] = useState([]);
  const [assigneeDraft, setAssigneeDraft] = useState("");

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (statusCsv) params.set("status", statusCsv);
      const response = await fetcher(`/admin/court-cases?${params.toString()}`);
      const data = await response.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || t("tasks.errorLoad"));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [fetcher, statusCsv, t]);

  const loadCase = useCallback(
    async (caseId) => {
      if (!caseId) return;
      setError("");
      try {
        const response = await fetcher(`/admin/court-cases/${caseId}`);
        const data = await response.json();
        setSelected(data || null);
        setCaseStatusDraft(data?.status || "");
        setScholarNameDraft(data?.scholar_name || "");
        setScholarContactDraft(data?.scholar_contact || "");
        setScholarIdDraft(data?.scholar_id || "");
        if (data?.scholar_id && String(Number(data.scholar_id)) === String(data.scholar_id)) {
          setSelectedScholarId(String(Number(data.scholar_id)));
        } else {
          setSelectedScholarId("");
        }
        setAssigneeDraft(String(data?.responsible_admin_id || ""));
      } catch (err) {
        setError(err.message || t("errors.requestFailed"));
      }
    },
    [fetcher, t],
  );

  const loadAdminAccounts = useCallback(async () => {
    if (!canAssignAny) {
      setAdminAccounts([]);
      return;
    }
    try {
      const response = await fetcher("/admin/admin-accounts");
      const data = await response.json();
      setAdminAccounts(Array.isArray(data) ? data : []);
    } catch (_err) {
      setAdminAccounts([]);
    }
  }, [canAssignAny, fetcher]);
  const loadScholars = useCallback(async () => {
    try {
      const response = await fetcher("/admin/scholars");
      const data = await response.json();
      setScholars(Array.isArray(data) ? data : []);
    } catch (_err) {
      setScholars([]);
    }
  }, [fetcher]);


  const handleUpdateCase = async () => {
    if (!selected?.id) return;
    const nextStatus = caseStatusDraft || selected?.status || "";
    setError("");
    try {
      const response = await fetcher(`/admin/court-cases/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: nextStatus || undefined,
          scholar_name: scholarNameDraft,
          scholar_contact: scholarContactDraft,
          scholar_id: scholarIdDraft,
        }),
      });
      const updated = await response.json();
      setSelected(updated || null);
      setCaseStatusDraft(updated?.status || "");
      setScholarNameDraft(updated?.scholar_name || "");
      setScholarContactDraft(updated?.scholar_contact || "");
      setScholarIdDraft(updated?.scholar_id || "");
      if (updated?.scholar_id && String(Number(updated.scholar_id)) === String(updated.scholar_id)) {
        setSelectedScholarId(String(Number(updated.scholar_id)));
      } else {
        setSelectedScholarId("");
      }
      await loadCase(selected.id);
      await loadItems();
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleUpdateCaseStatus = async () => {
    if (!selected?.id) return;
    const nextStatus = caseStatusDraft || selected?.status || "";
    if (!nextStatus) return;
    setError("");
    try {
      const response = await fetcher(`/admin/court-cases/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: String(nextStatus) }),
      });
      const updated = await response.json();
      setSelected(updated || null);
      setCaseStatusDraft(updated?.status || "");
      await loadCase(selected.id);
      await loadItems();
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleAssignResponsible = async () => {
    if (!selected?.id) return;
    setError("");
    const assigneeId = canAssignAny
      ? Number(assigneeDraft || 0)
      : Number(profile?.admin_account_id || 0);
    if (!assigneeId) return;
    try {
      await fetcher(`/admin/court-cases/${selected.id}/assign`, {
        method: "POST",
        body: JSON.stringify({ assignee_admin_id: assigneeId }),
      });
      await loadCase(selected.id);
      await loadItems();
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleDownloadEvidence = async (idx) => {
    if (!selected?.id) return;
    setError("");
    try {
      const response = await fetcher(
        `/admin/court-cases/${selected.id}/evidence/${idx}/download`,
      );
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename=([^;]+)/i);
      const filename = match ? match[1].replace(/\"/g, "") : `evidence_${idx}`;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  useEffect(() => {
    loadAdminAccounts();
  }, [loadAdminAccounts]);

  useEffect(() => {
    loadScholars();
  }, [loadScholars]);

  const columns = [
    { key: "case_number", title: t("courts.admin.caseNumber"), width: "140px" },
    {
      key: "status",
      title: t("courts.admin.status"),
      width: "140px",
      render: (row) => statusLabel(row.status),
    },
    {
      key: "responsible_admin_username",
      title: t("courts.admin.assignee"),
      width: "180px",
      render: (row) => row.responsible_admin_username || t("common.notAvailable"),
    },
    {
      key: "category",
      title: t("courts.admin.category"),
      width: "180px",
      render: (row) => categoryLabel(row.category),
    },
    { key: "plaintiff", title: t("courts.admin.plaintiff"), width: "200px" },
    { key: "defendant", title: t("courts.admin.defendant"), width: "200px" },
    {
      key: "created_at",
      title: t("courts.admin.created"),
      width: "200px",
      render: (row) => (row.created_at ? formatDateTime(row.created_at, language) : t("common.notAvailable")),
    },
  ];

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {error ? <Notice kind="error">{error}</Notice> : null}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "0.75rem",
          padding: "0.75rem",
          border: `1px solid ${COLORS.border}`,
          borderRadius: "12px",
          backgroundColor: "#f8fafc",
        }}
      >
        <strong style={{ marginRight: "0.5rem" }}>{t("tabs.courts")}</strong>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("courts.admin.status")}
          <input
            type="text"
            value={statusCsv}
            onChange={(e) => setStatusCsv(e.target.value)}
            placeholder="open,in_progress,closed"
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "220px" }}
          />
        </label>
        <button type="button" style={buttonStyle("ghost")} onClick={loadItems} disabled={loading}>
          {t("tasks.refresh")}
        </button>
      </div>
      {loading ? <div>{t("common.loading")}</div> : null}
      <Table
        columns={columns}
        rows={items}
        emptyText={t("tasks.empty")}
        rowKey="id"
        onRowClick={(row) => {
          setSelected(null);
          setCaseStatusDraft("");
          setScholarNameDraft("");
          setScholarContactDraft("");
          setScholarIdDraft("");
          loadCase(row.id);
        }}
      />

      {selected ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setSelected(null)}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: "1.25rem 1.5rem",
              borderRadius: "12px",
              minWidth: "420px",
              maxWidth: "980px",
              width: "92vw",
              maxHeight: "92vh",
              overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>
                {t("courts.admin.title")} № {selected.case_number || selected.id}
              </h3>
              <button type="button" style={buttonStyle("ghost")} onClick={() => setSelected(null)}>
                {t("tasks.close")}
              </button>
            </div>

            <div style={{ display: "grid", gap: "0.4rem", marginBottom: "1rem", color: COLORS.secondaryText }}>
              <div>
                <strong>{t("courts.admin.status")}:</strong> {statusLabel(selected.status)}
              </div>
              <div>
                <strong>{t("courts.admin.category")}:</strong> {categoryLabel(selected.category)}
              </div>
              <div>
                <strong>{t("courts.admin.plaintiff")}:</strong> {selected.plaintiff}
              </div>
              <div>
                <strong>{t("courts.admin.defendant")}:</strong> {selected.defendant}
              </div>
              <div>
                <strong>{t("courts.admin.assignee")}:</strong>{" "}
                {selected.responsible_admin_username || t("common.notAvailable")}
              </div>
            </div>

            <div
              style={{
                padding: "0.75rem",
                border: `1px solid ${COLORS.border}`,
                borderRadius: "10px",
                backgroundColor: "#eef2ff",
                display: "grid",
                gap: "0.6rem",
                marginBottom: "1rem",
              }}
            >
              <strong>{t("courts.admin.assignTitle")}</strong>
              {canAssignAny ? (
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  {t("courts.admin.assignee")}
                  <select
                    value={assigneeDraft}
                    onChange={(e) => setAssigneeDraft(e.target.value)}
                    style={{ padding: "0.35rem", borderRadius: "8px" }}
                    disabled={!canManage}
                  >
                    <option value="">{t("common.notAvailable")}</option>
                    {adminAccounts.map((account) => (
                      <option key={account.id} value={String(account.id)}>
                        {account.username}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <div>{t("courts.admin.assignSelf")}</div>
              )}
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button
                  type="button"
                  style={buttonStyle("primary")}
                  onClick={handleAssignResponsible}
                  disabled={!canManage}
                >
                  {t("courts.admin.assignAction")}
                </button>
              </div>
            </div>

            <div style={{ display: "grid", gap: "0.5rem", marginBottom: "1rem" }}>
              <h4 style={{ margin: 0 }}>{t("courts.admin.evidence")}</h4>
              {(selected.evidence || []).length ? (
                <div style={{ display: "grid", gap: "0.4rem" }}>
                  {(selected.evidence || []).map((item, idx) => (
                    <div
                      key={`${idx}-${item?.file_id || item?.url || "e"}`}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "0.5rem",
                        border: `1px solid ${COLORS.border}`,
                        borderRadius: "8px",
                        padding: "0.4rem 0.6rem",
                      }}
                    >
                      <div style={{ fontSize: "0.9rem" }}>
                        <strong>{item?.type || "file"}:</strong>{" "}
                        {item?.file_name || item?.url || item?.text || item?.file_id || "-"}
                      </div>
                      {item?.file_id ? (
                        <button
                          type="button"
                          style={buttonStyle("ghost")}
                          onClick={() => handleDownloadEvidence(idx)}
                        >
                          {t("common.download")}
                        </button>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: COLORS.secondaryText }}>{t("common.notAvailable")}</div>
              )}
            </div>

            <CourtCaseEditor
              t={t}
              caseData={selected}
              canManage={canManage}
              statusDraft={caseStatusDraft}
              setStatusDraft={setCaseStatusDraft}
              onStatusSubmit={handleUpdateCaseStatus}
              scholarNameDraft={scholarNameDraft}
              setScholarNameDraft={setScholarNameDraft}
              scholarContactDraft={scholarContactDraft}
              setScholarContactDraft={setScholarContactDraft}
              scholarIdDraft={scholarIdDraft}
              setScholarIdDraft={setScholarIdDraft}
              scholars={scholars}
              selectedScholarId={selectedScholarId}
              setSelectedScholarId={setSelectedScholarId}
              onSubmit={handleUpdateCase}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
};

const ContractsTab = ({ fetcher, profile }) => {
  const { t, language } = useI18n();
  const roleSet = useMemo(() => new Set(profile?.roles || []), [profile?.roles]);
  const canManage =
    roleSet.has("owner") ||
    roleSet.has("superadmin") ||
    roleSet.has("admin_work_items_manage");
  const canAssignAny = roleSet.has("owner") || roleSet.has("superadmin");
  const statusLabel = useCallback(
    (value) => {
      if (!value) return t("common.notAvailable");
      const key = `contracts.status.${value}`;
      const label = t(key);
      return label === key ? value : label;
    },
    [t],
  );

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusCsv, setStatusCsv] = useState("");
  const [selected, setSelected] = useState(null);
  const [contractStatusDraft, setContractStatusDraft] = useState("");
  const [scholarNameDraft, setScholarNameDraft] = useState("");
  const [scholarContactDraft, setScholarContactDraft] = useState("");
  const [scholarIdDraft, setScholarIdDraft] = useState("");
  const [scholars, setScholars] = useState([]);
  const [selectedScholarId, setSelectedScholarId] = useState("");
  const [adminAccounts, setAdminAccounts] = useState([]);
  const [assigneeDraft, setAssigneeDraft] = useState("");

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (statusCsv) params.set("status", statusCsv);
      const response = await fetcher(`/admin/contracts?${params.toString()}`);
      const data = await response.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || t("tasks.errorLoad"));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [fetcher, statusCsv, t]);

  const loadContract = useCallback(
    async (contractId) => {
      if (!contractId) return;
      setError("");
      try {
        const response = await fetcher(`/admin/contracts/${contractId}`);
        const data = await response.json();
        setSelected(data || null);
        setContractStatusDraft(data?.status || "");
        setScholarNameDraft(data?.scholar_name || "");
        setScholarContactDraft(data?.scholar_contact || "");
        setScholarIdDraft(data?.scholar_id || "");
        if (data?.scholar_id && String(Number(data.scholar_id)) === String(data.scholar_id)) {
          setSelectedScholarId(String(Number(data.scholar_id)));
        } else {
          setSelectedScholarId("");
        }
        setAssigneeDraft(String(data?.responsible_admin_id || ""));
      } catch (err) {
        setError(err.message || t("errors.requestFailed"));
      }
    },
    [fetcher, t],
  );

  const loadAdminAccounts = useCallback(async () => {
    if (!canAssignAny) {
      setAdminAccounts([]);
      return;
    }
    try {
      const response = await fetcher("/admin/admin-accounts");
      const data = await response.json();
      setAdminAccounts(Array.isArray(data) ? data : []);
    } catch (_err) {
      setAdminAccounts([]);
    }
  }, [canAssignAny, fetcher]);

  const loadScholars = useCallback(async () => {
    try {
      const response = await fetcher("/admin/scholars");
      const data = await response.json();
      setScholars(Array.isArray(data) ? data : []);
    } catch (_err) {
      setScholars([]);
    }
  }, [fetcher]);

  const handleUpdateContract = async () => {
    if (!selected?.id) return;
    const nextStatus = contractStatusDraft || selected?.status || "";
    setError("");
    try {
      const response = await fetcher(`/admin/contracts/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: nextStatus || undefined,
          scholar_name: scholarNameDraft,
          scholar_contact: scholarContactDraft,
          scholar_id: scholarIdDraft,
        }),
      });
      const updated = await response.json();
      setSelected(updated || null);
      setContractStatusDraft(updated?.status || "");
      setScholarNameDraft(updated?.scholar_name || "");
      setScholarContactDraft(updated?.scholar_contact || "");
      setScholarIdDraft(updated?.scholar_id || "");
      if (updated?.scholar_id && String(Number(updated.scholar_id)) === String(updated.scholar_id)) {
        setSelectedScholarId(String(Number(updated.scholar_id)));
      } else {
        setSelectedScholarId("");
      }
      await loadContract(selected.id);
      await loadItems();
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleDeleteContract = async () => {
    if (!selected?.id) return;
    if (!window.confirm(t("contracts.admin.deleteConfirm"))) return;
    setError("");
    try {
      await fetcher(`/admin/contracts/${selected.id}`, { method: "DELETE" });
      setSelected(null);
      await loadItems();
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleUpdateContractStatus = async () => {
    if (!selected?.id) return;
    const nextStatus = contractStatusDraft || selected?.status || "";
    if (!nextStatus) return;
    setError("");
    try {
      const response = await fetcher(`/admin/contracts/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: String(nextStatus) }),
      });
      const updated = await response.json();
      setSelected(updated || null);
      setContractStatusDraft(updated?.status || "");
      await loadContract(selected.id);
      await loadItems();
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  const handleAssignResponsible = async () => {
    if (!selected?.id) return;
    setError("");
    const assigneeId = canAssignAny
      ? Number(assigneeDraft || 0)
      : Number(profile?.admin_account_id || 0);
    if (!assigneeId) return;
    try {
      await fetcher(`/admin/contracts/${selected.id}/assign`, {
        method: "POST",
        body: JSON.stringify({ assignee_admin_id: assigneeId }),
      });
      await loadContract(selected.id);
      await loadItems();
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    }
  };

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  useEffect(() => {
    loadAdminAccounts();
  }, [loadAdminAccounts]);

  useEffect(() => {
    loadScholars();
  }, [loadScholars]);

  const contractTitle = (row) =>
    row?.data?.contract_title || row?.template_topic || row?.contract_type || `#${row?.id ?? ""}`;

  const columns = [
    { key: "id", title: "ID", width: "80px" },
    {
      key: "status",
      title: t("contracts.admin.status"),
      width: "160px",
      render: (row) => statusLabel(row.status),
    },
    {
      key: "responsible_admin_username",
      title: t("contracts.admin.assignee"),
      width: "180px",
      render: (row) => row.responsible_admin_username || t("common.notAvailable"),
    },
    {
      key: "title",
      title: t("contracts.admin.contractTitle"),
      width: "260px",
      render: (row) => contractTitle(row),
    },
    {
      key: "user_id",
      title: t("contracts.admin.owner"),
      width: "140px",
      render: (row) => row.user_id ?? t("common.notAvailable"),
    },
    {
      key: "created_at",
      title: t("contracts.admin.created"),
      width: "200px",
      render: (row) => (row.created_at ? formatDateTime(row.created_at, language) : t("common.notAvailable")),
    },
  ];

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {error ? <Notice kind="error">{error}</Notice> : null}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "0.75rem",
          padding: "0.75rem",
          border: `1px solid ${COLORS.border}`,
          borderRadius: "12px",
          backgroundColor: "#f8fafc",
        }}
      >
        <strong style={{ marginRight: "0.5rem" }}>{t("tabs.contracts")}</strong>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("contracts.admin.status")}
          <input
            type="text"
            value={statusCsv}
            onChange={(e) => setStatusCsv(e.target.value)}
            placeholder="draft,confirmed,sent_to_party"
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "220px" }}
          />
        </label>
        <button type="button" style={buttonStyle("ghost")} onClick={loadItems} disabled={loading}>
          {t("tasks.refresh")}
        </button>
      </div>
      {loading ? <div>{t("common.loading")}</div> : null}
      <Table
        columns={columns}
        rows={items}
        emptyText={t("tasks.empty")}
        rowKey="id"
        onRowClick={(row) => {
          setSelected(null);
          setContractStatusDraft("");
          setScholarNameDraft("");
          setScholarContactDraft("");
          setScholarIdDraft("");
          setSelectedScholarId("");
          setAssigneeDraft("");
          loadContract(row.id);
        }}
      />

      {selected ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setSelected(null)}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: "1.25rem 1.5rem",
              borderRadius: "12px",
              minWidth: "420px",
              maxWidth: "980px",
              width: "92vw",
              maxHeight: "92vh",
              overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>
                {t("contracts.admin.title")} № {selected.id}
              </h3>
              <button type="button" style={buttonStyle("ghost")} onClick={() => setSelected(null)}>
                {t("tasks.close")}
              </button>
            </div>

            <div style={{ display: "grid", gap: "0.4rem", marginBottom: "1rem", color: COLORS.secondaryText }}>
              <div>
                <strong>{t("contracts.admin.status")}:</strong> {statusLabel(selected.status)}
              </div>
              <div>
                <strong>{t("contracts.admin.contractTitle")}:</strong> {contractTitle(selected)}
              </div>
              <div>
                <strong>{t("contracts.admin.contractType")}:</strong> {selected.contract_type || t("common.notAvailable")}
              </div>
              <div>
                <strong>{t("contracts.admin.owner")}:</strong> {selected.user_id ?? t("common.notAvailable")}
              </div>
              <div>
                <strong>{t("contracts.admin.assignee")}:</strong>{" "}
                {selected.responsible_admin_username || t("common.notAvailable")}
              </div>
            </div>

            <div
              style={{
                padding: "0.75rem",
                border: `1px solid ${COLORS.border}`,
                borderRadius: "10px",
                backgroundColor: "#eef2ff",
                display: "grid",
                gap: "0.6rem",
                marginBottom: "1rem",
              }}
            >
              <strong>{t("contracts.admin.assignTitle")}</strong>
              {canAssignAny ? (
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  {t("contracts.admin.assignee")}
                  <select
                    value={assigneeDraft}
                    onChange={(e) => setAssigneeDraft(e.target.value)}
                    style={{ padding: "0.35rem", borderRadius: "8px" }}
                    disabled={!canManage}
                  >
                    <option value="">{t("common.notAvailable")}</option>
                    {adminAccounts.map((account) => (
                      <option key={account.id} value={String(account.id)}>
                        {account.username}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <div>{t("contracts.admin.assignSelf")}</div>
              )}
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button
                  type="button"
                  style={buttonStyle("primary")}
                  onClick={handleAssignResponsible}
                  disabled={!canManage}
                >
                  {t("contracts.admin.assignAction")}
                </button>
              </div>
            </div>

            <ContractEditor
              t={t}
              contractData={selected}
              canManage={canManage}
              statusDraft={contractStatusDraft}
              setStatusDraft={setContractStatusDraft}
              onStatusSubmit={handleUpdateContractStatus}
              scholarNameDraft={scholarNameDraft}
              setScholarNameDraft={setScholarNameDraft}
              scholarContactDraft={scholarContactDraft}
              setScholarContactDraft={setScholarContactDraft}
              scholarIdDraft={scholarIdDraft}
              setScholarIdDraft={setScholarIdDraft}
              scholars={scholars}
              selectedScholarId={selectedScholarId}
              setSelectedScholarId={setSelectedScholarId}
              onSubmit={handleUpdateContract}
              onDelete={handleDeleteContract}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
};

const ContractEditor = ({
  t,
  contractData,
  canManage,
  statusDraft,
  setStatusDraft,
  onStatusSubmit,
  scholarNameDraft,
  setScholarNameDraft,
  scholarContactDraft,
  setScholarContactDraft,
  scholarIdDraft,
  setScholarIdDraft,
  scholars,
  selectedScholarId,
  setSelectedScholarId,
  onSubmit,
  onDelete,
}) => {
  const handleSelectScholar = (value) => {
    setSelectedScholarId(value);
    const scholarId = Number(value || 0);
    const scholar = (scholars || []).find((item) => item.id === scholarId);
    if (scholar) {
      setScholarNameDraft(scholar.username || "");
      setScholarIdDraft(String(scholar.id));
      setScholarContactDraft(
        scholar.telegram_id ? String(scholar.telegram_id) : "",
      );
    }
  };

  const contractTitle =
    contractData?.data?.contract_title ||
    contractData?.template_topic ||
    contractData?.contract_type ||
    t("common.notAvailable");
  const counterparty =
    contractData?.data?.recipient_name ||
    contractData?.data?.recipient ||
    contractData?.data?.recipient_id ||
    t("common.notAvailable");

  return (
    <div
      style={{
        padding: "0.75rem",
        border: `1px solid ${COLORS.border}`,
        borderRadius: "10px",
        backgroundColor: "#f1f5f9",
        display: "grid",
        gap: "0.6rem",
        marginBottom: "1rem",
      }}
    >
      <strong>{t("contracts.admin.title")}</strong>
      {contractData ? (
        <>
          <div>
            <strong>{t("contracts.admin.contractTitle")}:</strong> {contractTitle}
          </div>
          <div>
            <strong>{t("contracts.admin.contractType")}:</strong>{" "}
            {contractData.contract_type || t("common.notAvailable")}
          </div>
          <div>
            <strong>{t("contracts.admin.owner")}:</strong>{" "}
            {contractData.user_id ?? t("common.notAvailable")}
          </div>
          <div>
            <strong>{t("contracts.admin.counterparty")}:</strong> {counterparty}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
            <span>{t("contracts.admin.statusValue")}</span>
            <select
              value={statusDraft || contractData?.status || ""}
              onChange={(e) => setStatusDraft(e.target.value)}
              style={{ padding: "0.35rem", borderRadius: "8px" }}
              disabled={!canManage}
            >
              {[
                "draft",
                "confirmed",
                "sent_to_party",
                "party_approved",
                "party_changes_requested",
                "signed",
                "sent_to_scholar",
                "scholar_send_failed",
                "sent",
              ].map((s) => (
                <option key={s} value={s}>
                  {resolveContractStatusLabel(t, s)}
                </option>
              ))}
            </select>
            <button
              type="button"
              style={buttonStyle("ghost")}
              onClick={onStatusSubmit}
              disabled={!canManage}
            >
              {t("contracts.admin.statusUpdate")}
            </button>
          </div>
          <div style={{ display: "grid", gap: "0.4rem" }}>
            <span>{t("contracts.admin.scholarSelect")}</span>
            <select
              value={selectedScholarId || ""}
              onChange={(e) => handleSelectScholar(e.target.value)}
              style={{ padding: "0.35rem", borderRadius: "8px" }}
              disabled={!canManage || !(scholars || []).length}
            >
              <option value="">{t("contracts.admin.scholarSelectPlaceholder")}</option>
              {(scholars || []).map((scholar) => (
                <option key={scholar.id} value={String(scholar.id)}>
                  {scholar.username}
                </option>
              ))}
            </select>
            {!(scholars || []).length ? (
              <div style={{ color: COLORS.secondaryText }}>
                {t("contracts.admin.scholarEmpty")}
              </div>
            ) : null}
            <span>{t("contracts.admin.scholarName")}</span>
            <input
              value={scholarNameDraft}
              onChange={(e) => setScholarNameDraft(e.target.value)}
              style={{ padding: "0.4rem", borderRadius: "8px" }}
              disabled={!canManage}
            />
            <span>{t("contracts.admin.scholarContact")}</span>
            <input
              value={scholarContactDraft}
              onChange={(e) => setScholarContactDraft(e.target.value)}
              style={{ padding: "0.4rem", borderRadius: "8px" }}
              disabled={!canManage}
            />
            <span>{t("contracts.admin.scholarId")}</span>
            <input
              value={scholarIdDraft}
              onChange={(e) => setScholarIdDraft(e.target.value)}
              style={{ padding: "0.4rem", borderRadius: "8px" }}
              disabled={!canManage}
            />
            <button
              type="button"
              style={buttonStyle("primary")}
              onClick={onSubmit}
              disabled={!canManage}
            >
              {t("contracts.admin.update")}
            </button>
            {onDelete ? (
              <button
                type="button"
                style={buttonStyle("danger")}
                onClick={onDelete}
                disabled={!canManage}
              >
                {t("contracts.admin.delete")}
              </button>
            ) : null}
          </div>
          {contractData?.rendered_text ? (
            <div style={{ display: "grid", gap: "0.3rem" }}>
              <strong>{t("contracts.admin.text")}</strong>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", maxHeight: "240px", overflow: "auto" }}>
                {contractData.rendered_text}
              </pre>
            </div>
          ) : null}
        </>
      ) : (
        <div style={{ color: COLORS.secondaryText }}>{t("common.loading")}</div>
      )}
    </div>
  );
};

const GoodDeedsTab = ({ fetcher, canDecide }) => {
  const { t, language } = useI18n();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusCsv, setStatusCsv] = useState("pending,needs_clarification");
  const [cityFilter, setCityFilter] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [decisionStatus, setDecisionStatus] = useState("approved");
  const [decisionCategory, setDecisionCategory] = useState("");
  const [decisionComment, setDecisionComment] = useState("");
  const [saving, setSaving] = useState(false);

  const decisionOptions = ["approved", "needs_clarification", "rejected"];
  const categoryOptions = ["zakat", "fitr", "sadaqa"];

  const renderUser = useCallback(
    (row) => {
      if (row?.user_full_name) return row.user_full_name;
      if (row?.user_email) return row.user_email;
      if (row?.user_phone) return row.user_phone;
      if (row?.user_id) return `#${row.user_id}`;
      return t("common.notAvailable");
    },
    [t],
  );

  const formatAmount = useCallback(
    (amount) => {
      if (Number.isFinite(amount)) {
        return amount.toFixed(2);
      }
      if (amount === 0) {
        return "0";
      }
      return amount || t("common.notAvailable");
    },
    [t],
  );

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (statusCsv.trim()) params.set("status", statusCsv.trim());
      if (cityFilter.trim()) params.set("city", cityFilter.trim());
      if (countryFilter.trim()) params.set("country", countryFilter.trim());
      const response = await fetcher(`/admin/good-deeds?${params.toString()}`);
      const data = await response.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [fetcher, statusCsv, cityFilter, countryFilter, t]);

  const loadSelected = useCallback(
    async (deedId) => {
      if (!deedId) return;
      setError("");
      try {
        const response = await fetcher(`/admin/good-deeds/${deedId}`);
        const data = await response.json();
        setSelected(data || null);
      } catch (err) {
        setError(err.message || t("errors.requestFailed"));
      }
    },
    [fetcher, t],
  );

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      return;
    }
    loadSelected(selectedId);
  }, [selectedId, loadSelected]);

  useEffect(() => {
    if (!selected) return;
    setDecisionStatus("approved");
    setDecisionCategory(selected?.approved_category || "");
    setDecisionComment("");
  }, [selected?.id]);

  const handleClose = useCallback(() => {
    setSelectedId(null);
    setSelected(null);
  }, []);

  const handleDecisionSubmit = async () => {
    if (!selectedId) return;
    setSaving(true);
    setError("");
    try {
      const payload = {
        status: decisionStatus,
        review_comment: decisionComment,
      };
      if (decisionStatus === "approved") {
        payload.approved_category = decisionCategory;
      }
      const response = await fetcher(`/admin/good-deeds/${selectedId}/decision`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      setSelected(data || null);
      setItems((prev) =>
        prev.map((item) => (item.id === data.id ? data : item)),
      );
      setDecisionComment("");
      setDecisionCategory(data?.approved_category || decisionCategory);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    } finally {
      setSaving(false);
    }
  };

  const downloadAttachment = useCallback(
    async (path, fallbackName) => {
      setError("");
      try {
        const response = await fetcher(path);
        const blob = await response.blob();
        const disposition = response.headers.get("content-disposition") || "";
        const match = disposition.match(/filename=([^;]+)/i);
        const filename = match ? match[1].replace(/\"/g, "") : fallbackName;
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename || fallbackName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      } catch (err) {
        setError(err.message || t("errors.requestFailed"));
      }
    },
    [fetcher, t],
  );

  const columns = useMemo(
    () => [
      { key: "id", title: t("goodDeeds.columns.id"), width: "90px" },
      { key: "title", title: t("goodDeeds.columns.title"), width: "240px" },
      {
        key: "user",
        title: t("goodDeeds.columns.user"),
        width: "180px",
        render: (row) => renderUser(row),
      },
      {
        key: "city",
        title: t("goodDeeds.columns.city"),
        width: "160px",
        render: (row) => row.city || t("common.notAvailable"),
      },
      {
        key: "country",
        title: t("goodDeeds.columns.country"),
        width: "160px",
        render: (row) => row.country || t("common.notAvailable"),
      },
      {
        key: "status",
        title: t("goodDeeds.columns.status"),
        width: "160px",
        render: (row) => resolveGoodDeedStatusLabel(t, row.status),
      },
      {
        key: "created_at",
        title: t("goodDeeds.columns.created"),
        width: "200px",
        render: (row) =>
          row.created_at
            ? formatDateTime(row.created_at, language)
            : t("common.notAvailable"),
      },
    ],
    [language, renderUser, t],
  );

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {error ? <Notice kind="error">{error}</Notice> : null}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "0.75rem",
          padding: "0.75rem",
          border: `1px solid ${COLORS.border}`,
          borderRadius: "12px",
          backgroundColor: "#f8fafc",
        }}
      >
        <strong style={{ marginRight: "0.5rem" }}>{t("goodDeeds.title")}</strong>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("goodDeeds.filters.status")}
          <input
            type="text"
            value={statusCsv}
            onChange={(e) => setStatusCsv(e.target.value)}
            placeholder="pending,needs_clarification"
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "220px" }}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("goodDeeds.filters.city")}
          <input
            type="text"
            value={cityFilter}
            onChange={(e) => setCityFilter(e.target.value)}
            placeholder={t("goodDeeds.filters.city")}
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "180px" }}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("goodDeeds.filters.country")}
          <input
            type="text"
            value={countryFilter}
            onChange={(e) => setCountryFilter(e.target.value)}
            placeholder={t("goodDeeds.filters.country")}
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "180px" }}
          />
        </label>
        <button type="button" style={buttonStyle("ghost")} onClick={loadItems} disabled={loading}>
          {t("tasks.refresh")}
        </button>
      </div>
      {loading ? <div>{t("common.loading")}</div> : null}
      <Table
        columns={columns}
        rows={items}
        emptyText={t("goodDeeds.listEmpty")}
        rowKey="id"
        onRowClick={(row) => {
          setSelectedId(row.id);
          setSelected(null);
          setDecisionComment("");
          setDecisionCategory(row?.approved_category || "");
          setDecisionStatus("approved");
        }}
      />

      {selectedId ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={handleClose}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: "1.25rem 1.5rem",
              borderRadius: "12px",
              minWidth: "420px",
              maxWidth: "980px",
              width: "92vw",
              maxHeight: "92vh",
              overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>
                {t("goodDeeds.detail.title")} № {selectedId}
              </h3>
              <button type="button" style={buttonStyle("ghost")} onClick={handleClose}>
                {t("tasks.close")}
              </button>
            </div>

            {selected ? (
              <div style={{ display: "grid", gap: "0.4rem", marginBottom: "1rem", color: COLORS.secondaryText }}>
                <div>
                  <strong>{t("goodDeeds.detail.user")}:</strong> {renderUser(selected)}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.phone")}:</strong>{" "}
                  {selected.user_phone || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.email")}:</strong>{" "}
                  {selected.user_email || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.description")}:</strong>{" "}
                  {selected.description || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.helpType")}:</strong>{" "}
                  {resolveGoodDeedHelpTypeLabel(t, selected.help_type)}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.amount")}:</strong>{" "}
                  {formatAmount(selected.amount)}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.comment")}:</strong>{" "}
                  {selected.comment || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.status")}:</strong>{" "}
                  {resolveGoodDeedStatusLabel(t, selected.status)}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.approvedCategory")}:</strong>{" "}
                  {selected.approved_category
                    ? resolveGoodDeedCategoryLabel(t, selected.approved_category)
                    : t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.reviewComment")}:</strong>{" "}
                  {selected.review_comment || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.created")}:</strong>{" "}
                  {selected.created_at
                    ? formatDateTime(selected.created_at, language)
                    : t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.updated")}:</strong>{" "}
                  {selected.updated_at
                    ? formatDateTime(selected.updated_at, language)
                    : t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.approvedAt")}:</strong>{" "}
                  {selected.approved_at
                    ? formatDateTime(selected.approved_at, language)
                    : t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.completedAt")}:</strong>{" "}
                  {selected.completed_at
                    ? formatDateTime(selected.completed_at, language)
                    : t("common.notAvailable")}
                </div>
              </div>
            ) : (
              <div style={{ marginBottom: "1rem", color: COLORS.secondaryText }}>
                {t("common.loading")}
              </div>
            )}

            {selected?.clarification_text || selected?.clarification_attachment ? (
              <div
                style={{
                  padding: "0.75rem",
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: "10px",
                  backgroundColor: "#eef2ff",
                  display: "grid",
                  gap: "0.5rem",
                  marginBottom: "1rem",
                }}
              >
                <strong>{t("goodDeeds.detail.clarificationText")}</strong>
                <div style={{ color: COLORS.secondaryText, whiteSpace: "pre-wrap" }}>
                  {selected?.clarification_text || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.clarificationAttachment")}:</strong>{" "}
                  {selected?.clarification_attachment?.filename ||
                    selected?.clarification_attachment?.link ||
                    t("common.notAvailable")}
                </div>
                {selected?.clarification_attachment?.link ? (
                  <a href={selected.clarification_attachment.link} target="_blank" rel="noreferrer">
                    {selected.clarification_attachment.link}
                  </a>
                ) : null}
                {selected?.clarification_attachment?.file_id ? (
                  <button
                    type="button"
                    style={buttonStyle("ghost")}
                    onClick={() =>
                      downloadAttachment(
                        `/admin/good-deeds/${selectedId}/clarification/download`,
                        `clarification_${selectedId}`,
                      )
                    }
                  >
                    {t("goodDeeds.downloadClarification")}
                  </button>
                ) : null}
              </div>
            ) : null}

            {canDecide ? (
              <div
                style={{
                  padding: "0.75rem",
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: "10px",
                  backgroundColor: "#f8fafc",
                  display: "grid",
                  gap: "0.75rem",
                  marginBottom: "1rem",
                }}
              >
                <strong>{t("goodDeeds.decision.title")}</strong>
                <label style={{ display: "grid", gap: "0.3rem" }}>
                  <span>{t("goodDeeds.decision.status")}</span>
                  <select
                    value={decisionStatus}
                    onChange={(e) => setDecisionStatus(e.target.value)}
                    style={{ padding: "0.4rem", borderRadius: "8px" }}
                  >
                    {decisionOptions.map((status) => (
                      <option key={status} value={status}>
                        {resolveLabel(t, "goodDeeds.decisionStatuses", status)}
                      </option>
                    ))}
                  </select>
                </label>
                {decisionStatus === "approved" ? (
                  <label style={{ display: "grid", gap: "0.3rem" }}>
                    <span>{t("goodDeeds.decision.category")}</span>
                    <select
                      value={decisionCategory}
                      onChange={(e) => setDecisionCategory(e.target.value)}
                      style={{ padding: "0.4rem", borderRadius: "8px" }}
                    >
                      <option value="">{t("common.notAvailable")}</option>
                      {categoryOptions.map((category) => (
                        <option key={category} value={category}>
                          {resolveGoodDeedCategoryLabel(t, category)}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                <label style={{ display: "grid", gap: "0.3rem" }}>
                  <span>{t("goodDeeds.decision.comment")}</span>
                  <textarea
                    rows={3}
                    value={decisionComment}
                    onChange={(e) => setDecisionComment(e.target.value)}
                    style={{
                      padding: "0.6rem",
                      borderRadius: "10px",
                      border: `1px solid ${COLORS.border}`,
                    }}
                  />
                </label>
                <button
                  type="button"
                  style={buttonStyle("primary")}
                  onClick={handleDecisionSubmit}
                  disabled={saving}
                >
                  {t("goodDeeds.decision.submit")}
                </button>
              </div>
            ) : null}

            <div style={{ display: "grid", gap: "0.5rem" }}>
              <h4 style={{ margin: 0 }}>{t("goodDeeds.historyTitle")}</h4>
              <HistoryList items={selected?.history} t={t} language={language} />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

const GoodDeedNeedyTab = ({ fetcher, canDecide }) => {
  const { t, language } = useI18n();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusCsv, setStatusCsv] = useState("pending,needs_clarification");
  const [cityFilter, setCityFilter] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [decisionStatus, setDecisionStatus] = useState("approved");
  const [decisionComment, setDecisionComment] = useState("");
  const [saving, setSaving] = useState(false);

  const decisionOptions = ["approved", "needs_clarification", "rejected"];

  const renderUser = useCallback(
    (row) => {
      if (row?.user_full_name) return row.user_full_name;
      if (row?.user_email) return row.user_email;
      if (row?.user_phone) return row.user_phone;
      if (row?.created_by_user_id) return `#${row.created_by_user_id}`;
      return t("common.notAvailable");
    },
    [t],
  );

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (statusCsv.trim()) params.set("status", statusCsv.trim());
      if (cityFilter.trim()) params.set("city", cityFilter.trim());
      if (countryFilter.trim()) params.set("country", countryFilter.trim());
      const response = await fetcher(`/admin/good-deeds/needy?${params.toString()}`);
      const data = await response.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [fetcher, statusCsv, cityFilter, countryFilter, t]);

  const loadSelected = useCallback(
    async (needyId) => {
      if (!needyId) return;
      setError("");
      try {
        const response = await fetcher(`/admin/good-deeds/needy/${needyId}`);
        const data = await response.json();
        setSelected(data || null);
      } catch (err) {
        setError(err.message || t("errors.requestFailed"));
      }
    },
    [fetcher, t],
  );

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      return;
    }
    loadSelected(selectedId);
  }, [selectedId, loadSelected]);

  useEffect(() => {
    if (!selected) return;
    setDecisionStatus("approved");
    setDecisionComment("");
  }, [selected?.id]);

  const handleClose = useCallback(() => {
    setSelectedId(null);
    setSelected(null);
  }, []);

  const handleDecisionSubmit = async () => {
    if (!selectedId) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetcher(`/admin/good-deeds/needy/${selectedId}/decision`, {
        method: "PATCH",
        body: JSON.stringify({
          status: decisionStatus,
          review_comment: decisionComment,
        }),
      });
      const data = await response.json();
      setSelected(data || null);
      setItems((prev) =>
        prev.map((item) => (item.id === data.id ? data : item)),
      );
      setDecisionComment("");
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    } finally {
      setSaving(false);
    }
  };

  const columns = useMemo(
    () => [
      { key: "id", title: t("goodDeeds.columns.id"), width: "90px" },
      {
        key: "person_type",
        title: t("goodDeeds.columns.person"),
        width: "160px",
        render: (row) => row.person_type || t("common.notAvailable"),
      },
      {
        key: "city",
        title: t("goodDeeds.columns.city"),
        width: "160px",
        render: (row) => row.city || t("common.notAvailable"),
      },
      {
        key: "country",
        title: t("goodDeeds.columns.country"),
        width: "160px",
        render: (row) => row.country || t("common.notAvailable"),
      },
      {
        key: "status",
        title: t("goodDeeds.columns.status"),
        width: "160px",
        render: (row) => resolveGoodDeedStatusLabel(t, row.status),
      },
      {
        key: "created_at",
        title: t("goodDeeds.columns.created"),
        width: "200px",
        render: (row) =>
          row.created_at
            ? formatDateTime(row.created_at, language)
            : t("common.notAvailable"),
      },
    ],
    [language, t],
  );

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {error ? <Notice kind="error">{error}</Notice> : null}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "0.75rem",
          padding: "0.75rem",
          border: `1px solid ${COLORS.border}`,
          borderRadius: "12px",
          backgroundColor: "#f8fafc",
        }}
      >
        <strong style={{ marginRight: "0.5rem" }}>{t("shariahControl.tabs.needy")}</strong>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("goodDeeds.filters.status")}
          <input
            type="text"
            value={statusCsv}
            onChange={(e) => setStatusCsv(e.target.value)}
            placeholder="pending,needs_clarification"
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "220px" }}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("goodDeeds.filters.city")}
          <input
            type="text"
            value={cityFilter}
            onChange={(e) => setCityFilter(e.target.value)}
            placeholder={t("goodDeeds.filters.city")}
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "180px" }}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("goodDeeds.filters.country")}
          <input
            type="text"
            value={countryFilter}
            onChange={(e) => setCountryFilter(e.target.value)}
            placeholder={t("goodDeeds.filters.country")}
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "180px" }}
          />
        </label>
        <button type="button" style={buttonStyle("ghost")} onClick={loadItems} disabled={loading}>
          {t("tasks.refresh")}
        </button>
      </div>
      {loading ? <div>{t("common.loading")}</div> : null}
      <Table
        columns={columns}
        rows={items}
        emptyText={t("goodDeeds.needyEmpty")}
        rowKey="id"
        onRowClick={(row) => {
          setSelectedId(row.id);
          setSelected(null);
          setDecisionComment("");
          setDecisionStatus("approved");
        }}
      />

      {selectedId ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={handleClose}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: "1.25rem 1.5rem",
              borderRadius: "12px",
              minWidth: "420px",
              maxWidth: "980px",
              width: "92vw",
              maxHeight: "92vh",
              overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>
                {t("goodDeeds.detail.needyTitle")} № {selectedId}
              </h3>
              <button type="button" style={buttonStyle("ghost")} onClick={handleClose}>
                {t("tasks.close")}
              </button>
            </div>

            {selected ? (
              <div style={{ display: "grid", gap: "0.4rem", marginBottom: "1rem", color: COLORS.secondaryText }}>
                <div>
                  <strong>{t("goodDeeds.detail.user")}:</strong> {renderUser(selected)}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.phone")}:</strong>{" "}
                  {selected.user_phone || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.email")}:</strong>{" "}
                  {selected.user_email || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.columns.person")}:</strong>{" "}
                  {selected.person_type || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.filters.city")}:</strong>{" "}
                  {selected.city || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.filters.country")}:</strong>{" "}
                  {selected.country || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.reason")}:</strong>{" "}
                  {selected.reason || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.allowZakat")}:</strong>{" "}
                  {selected.allow_zakat ? t("common.yes") : t("common.no")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.allowFitr")}:</strong>{" "}
                  {selected.allow_fitr ? t("common.yes") : t("common.no")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.sadaqaOnly")}:</strong>{" "}
                  {selected.sadaqa_only ? t("common.yes") : t("common.no")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.comment")}:</strong>{" "}
                  {selected.comment || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.status")}:</strong>{" "}
                  {resolveGoodDeedStatusLabel(t, selected.status)}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.reviewComment")}:</strong>{" "}
                  {selected.review_comment || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.created")}:</strong>{" "}
                  {selected.created_at
                    ? formatDateTime(selected.created_at, language)
                    : t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.updated")}:</strong>{" "}
                  {selected.updated_at
                    ? formatDateTime(selected.updated_at, language)
                    : t("common.notAvailable")}
                </div>
              </div>
            ) : (
              <div style={{ marginBottom: "1rem", color: COLORS.secondaryText }}>
                {t("common.loading")}
              </div>
            )}

            {canDecide ? (
              <div
                style={{
                  padding: "0.75rem",
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: "10px",
                  backgroundColor: "#f8fafc",
                  display: "grid",
                  gap: "0.75rem",
                  marginBottom: "1rem",
                }}
              >
                <strong>{t("goodDeeds.decision.title")}</strong>
                <label style={{ display: "grid", gap: "0.3rem" }}>
                  <span>{t("goodDeeds.decision.status")}</span>
                  <select
                    value={decisionStatus}
                    onChange={(e) => setDecisionStatus(e.target.value)}
                    style={{ padding: "0.4rem", borderRadius: "8px" }}
                  >
                    {decisionOptions.map((status) => (
                      <option key={status} value={status}>
                        {resolveLabel(t, "goodDeeds.decisionStatuses", status)}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ display: "grid", gap: "0.3rem" }}>
                  <span>{t("goodDeeds.decision.comment")}</span>
                  <textarea
                    rows={3}
                    value={decisionComment}
                    onChange={(e) => setDecisionComment(e.target.value)}
                    style={{
                      padding: "0.6rem",
                      borderRadius: "10px",
                      border: `1px solid ${COLORS.border}`,
                    }}
                  />
                </label>
                <button
                  type="button"
                  style={buttonStyle("primary")}
                  onClick={handleDecisionSubmit}
                  disabled={saving}
                >
                  {t("goodDeeds.decision.submit")}
                </button>
              </div>
            ) : null}

            <div style={{ display: "grid", gap: "0.5rem" }}>
              <h4 style={{ margin: 0 }}>{t("goodDeeds.historyTitle")}</h4>
              <HistoryList items={selected?.history} t={t} language={language} />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

const GoodDeedConfirmationsTab = ({ fetcher, canDecide }) => {
  const { t, language } = useI18n();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusCsv, setStatusCsv] = useState("pending");
  const [goodDeedFilter, setGoodDeedFilter] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [decisionStatus, setDecisionStatus] = useState("approved");
  const [decisionComment, setDecisionComment] = useState("");
  const [saving, setSaving] = useState(false);

  const decisionOptions = ["approved", "rejected"];

  const renderUser = useCallback(
    (row) => {
      if (row?.user_full_name) return row.user_full_name;
      if (row?.user_email) return row.user_email;
      if (row?.user_phone) return row.user_phone;
      if (row?.created_by_user_id) return `#${row.created_by_user_id}`;
      return t("common.notAvailable");
    },
    [t],
  );

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (statusCsv.trim()) params.set("status", statusCsv.trim());
      if (goodDeedFilter.trim()) {
        const idValue = Number.parseInt(goodDeedFilter.trim(), 10);
        if (!Number.isNaN(idValue)) {
          params.set("good_deed_id", String(idValue));
        }
      }
      const response = await fetcher(`/admin/good-deeds/confirmations?${params.toString()}`);
      const data = await response.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [fetcher, statusCsv, goodDeedFilter, t]);

  const loadSelected = useCallback(
    async (confirmationId) => {
      if (!confirmationId) return;
      setError("");
      try {
        const response = await fetcher(`/admin/good-deeds/confirmations/${confirmationId}`);
        const data = await response.json();
        setSelected(data || null);
      } catch (err) {
        setError(err.message || t("errors.requestFailed"));
      }
    },
    [fetcher, t],
  );

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      return;
    }
    loadSelected(selectedId);
  }, [selectedId, loadSelected]);

  useEffect(() => {
    if (!selected) return;
    setDecisionStatus("approved");
    setDecisionComment("");
  }, [selected?.id]);

  const handleClose = useCallback(() => {
    setSelectedId(null);
    setSelected(null);
  }, []);

  const handleDecisionSubmit = async () => {
    if (!selectedId) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetcher(`/admin/good-deeds/confirmations/${selectedId}/decision`, {
        method: "PATCH",
        body: JSON.stringify({
          status: decisionStatus,
          review_comment: decisionComment,
        }),
      });
      const data = await response.json();
      setSelected(data || null);
      setItems((prev) =>
        prev.map((item) => (item.id === data.id ? data : item)),
      );
      setDecisionComment("");
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    } finally {
      setSaving(false);
    }
  };

  const downloadAttachment = useCallback(
    async (path, fallbackName) => {
      setError("");
      try {
        const response = await fetcher(path);
        const blob = await response.blob();
        const disposition = response.headers.get("content-disposition") || "";
        const match = disposition.match(/filename=([^;]+)/i);
        const filename = match ? match[1].replace(/\"/g, "") : fallbackName;
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename || fallbackName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      } catch (err) {
        setError(err.message || t("errors.requestFailed"));
      }
    },
    [fetcher, t],
  );

  const columns = useMemo(
    () => [
      { key: "id", title: t("goodDeeds.columns.id"), width: "90px" },
      {
        key: "good_deed_title",
        title: t("goodDeeds.columns.goodDeed"),
        width: "240px",
        render: (row) =>
          row.good_deed_title || (row.good_deed_id ? `#${row.good_deed_id}` : t("common.notAvailable")),
      },
      {
        key: "status",
        title: t("goodDeeds.columns.status"),
        width: "160px",
        render: (row) => resolveGoodDeedStatusLabel(t, row.status),
      },
      {
        key: "user",
        title: t("goodDeeds.columns.user"),
        width: "180px",
        render: (row) => renderUser(row),
      },
      {
        key: "created_at",
        title: t("goodDeeds.columns.created"),
        width: "200px",
        render: (row) =>
          row.created_at
            ? formatDateTime(row.created_at, language)
            : t("common.notAvailable"),
      },
    ],
    [language, renderUser, t],
  );

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {error ? <Notice kind="error">{error}</Notice> : null}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "0.75rem",
          padding: "0.75rem",
          border: `1px solid ${COLORS.border}`,
          borderRadius: "12px",
          backgroundColor: "#f8fafc",
        }}
      >
        <strong style={{ marginRight: "0.5rem" }}>{t("shariahControl.tabs.confirmations")}</strong>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("goodDeeds.filters.status")}
          <input
            type="text"
            value={statusCsv}
            onChange={(e) => setStatusCsv(e.target.value)}
            placeholder="pending"
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "200px" }}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("goodDeeds.filters.deedId")}
          <input
            type="text"
            value={goodDeedFilter}
            onChange={(e) => setGoodDeedFilter(e.target.value)}
            placeholder="123"
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "120px" }}
          />
        </label>
        <button type="button" style={buttonStyle("ghost")} onClick={loadItems} disabled={loading}>
          {t("tasks.refresh")}
        </button>
      </div>
      {loading ? <div>{t("common.loading")}</div> : null}
      <Table
        columns={columns}
        rows={items}
        emptyText={t("goodDeeds.confirmationsEmpty")}
        rowKey="id"
        onRowClick={(row) => {
          setSelectedId(row.id);
          setSelected(null);
          setDecisionComment("");
          setDecisionStatus("approved");
        }}
      />

      {selectedId ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={handleClose}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: "1.25rem 1.5rem",
              borderRadius: "12px",
              minWidth: "420px",
              maxWidth: "980px",
              width: "92vw",
              maxHeight: "92vh",
              overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>
                {t("goodDeeds.detail.confirmationTitle")} № {selectedId}
              </h3>
              <button type="button" style={buttonStyle("ghost")} onClick={handleClose}>
                {t("tasks.close")}
              </button>
            </div>

            {selected ? (
              <div style={{ display: "grid", gap: "0.4rem", marginBottom: "1rem", color: COLORS.secondaryText }}>
                <div>
                  <strong>{t("goodDeeds.detail.goodDeed")}:</strong>{" "}
                  {selected.good_deed_title || `#${selected.good_deed_id}`}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.status")}:</strong>{" "}
                  {resolveGoodDeedStatusLabel(t, selected.status)}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.user")}:</strong> {renderUser(selected)}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.phone")}:</strong>{" "}
                  {selected.user_phone || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.email")}:</strong>{" "}
                  {selected.user_email || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.text")}:</strong>{" "}
                  {selected.text || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.attachment")}:</strong>{" "}
                  {selected.attachment?.filename ||
                    selected.attachment?.link ||
                    t("common.notAvailable")}
                </div>
                {selected.attachment?.link ? (
                  <a href={selected.attachment.link} target="_blank" rel="noreferrer">
                    {selected.attachment.link}
                  </a>
                ) : null}
                {selected.attachment?.file_id ? (
                  <button
                    type="button"
                    style={buttonStyle("ghost")}
                    onClick={() =>
                      downloadAttachment(
                        `/admin/good-deeds/confirmations/${selectedId}/download`,
                        `confirmation_${selectedId}`,
                      )
                    }
                  >
                    {t("goodDeeds.downloadAttachment")}
                  </button>
                ) : null}
                <div>
                  <strong>{t("goodDeeds.detail.reviewComment")}:</strong>{" "}
                  {selected.review_comment || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.created")}:</strong>{" "}
                  {selected.created_at
                    ? formatDateTime(selected.created_at, language)
                    : t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("goodDeeds.detail.updated")}:</strong>{" "}
                  {selected.updated_at
                    ? formatDateTime(selected.updated_at, language)
                    : t("common.notAvailable")}
                </div>
              </div>
            ) : (
              <div style={{ marginBottom: "1rem", color: COLORS.secondaryText }}>
                {t("common.loading")}
              </div>
            )}

            {canDecide ? (
              <div
                style={{
                  padding: "0.75rem",
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: "10px",
                  backgroundColor: "#f8fafc",
                  display: "grid",
                  gap: "0.75rem",
                  marginBottom: "1rem",
                }}
              >
                <strong>{t("goodDeeds.decision.title")}</strong>
                <label style={{ display: "grid", gap: "0.3rem" }}>
                  <span>{t("goodDeeds.decision.status")}</span>
                  <select
                    value={decisionStatus}
                    onChange={(e) => setDecisionStatus(e.target.value)}
                    style={{ padding: "0.4rem", borderRadius: "8px" }}
                  >
                    {decisionOptions.map((status) => (
                      <option key={status} value={status}>
                        {resolveLabel(t, "goodDeeds.decisionStatuses", status)}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ display: "grid", gap: "0.3rem" }}>
                  <span>{t("goodDeeds.decision.comment")}</span>
                  <textarea
                    rows={3}
                    value={decisionComment}
                    onChange={(e) => setDecisionComment(e.target.value)}
                    style={{
                      padding: "0.6rem",
                      borderRadius: "10px",
                      border: `1px solid ${COLORS.border}`,
                    }}
                  />
                </label>
                <button
                  type="button"
                  style={buttonStyle("primary")}
                  onClick={handleDecisionSubmit}
                  disabled={saving}
                >
                  {t("goodDeeds.decision.submit")}
                </button>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
};

const ShariahApplicationsTab = ({ fetcher, canManage }) => {
  const { t, language } = useI18n();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusCsv, setStatusCsv] = useState("pending_intro,meeting_scheduled");
  const [selectedId, setSelectedId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [scheduleType, setScheduleType] = useState("video");
  const [scheduleLink, setScheduleLink] = useState("");
  const [scheduleAt, setScheduleAt] = useState("");
  const [decisionStatus, setDecisionStatus] = useState("approved");
  const [decisionComment, setDecisionComment] = useState("");
  const [decisionRoles, setDecisionRoles] = useState([]);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [savingDecision, setSavingDecision] = useState(false);

  const meetingOptions = ["video", "audio"];
  const decisionOptions = ["approved", "observer", "rejected"];
  const roleOptions = [
    "tz_courts",
    "tz_contracts",
    "tz_good_deeds",
    "tz_execution",
    "shariah_chief",
  ];

  const renderUser = useCallback(
    (row) => {
      if (row?.user_full_name) return row.user_full_name;
      if (row?.user_email) return row.user_email;
      if (row?.user_phone) return row.user_phone;
      if (row?.user_id) return `#${row.user_id}`;
      return t("common.notAvailable");
    },
    [t],
  );

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (statusCsv.trim()) params.set("status", statusCsv.trim());
      const response = await fetcher(`/admin/shariah-applications?${params.toString()}`);
      const data = await response.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [fetcher, statusCsv, t]);

  const loadSelected = useCallback(
    async (applicationId) => {
      if (!applicationId) return;
      setError("");
      try {
        const response = await fetcher(`/admin/shariah-applications/${applicationId}`);
        const data = await response.json();
        setSelected(data || null);
        setScheduleType(data?.meeting_type || "video");
        setScheduleLink(data?.meeting_link || "");
        setScheduleAt(toLocalInputValue(data?.meeting_at));
        setDecisionStatus("approved");
        setDecisionComment("");
        setDecisionRoles(
          Array.isArray(data?.assigned_roles)
            ? data.assigned_roles.filter((role) => roleOptions.includes(role))
            : [],
        );
      } catch (err) {
        setError(err.message || t("errors.requestFailed"));
      }
    },
    [fetcher, t],
  );

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      return;
    }
    loadSelected(selectedId);
  }, [selectedId, loadSelected]);

  useEffect(() => {
    if (decisionStatus !== "approved") {
      setDecisionRoles([]);
    }
  }, [decisionStatus]);

  const handleClose = useCallback(() => {
    setSelectedId(null);
    setSelected(null);
  }, []);

  const handleScheduleSubmit = async () => {
    if (!selectedId) return;
    setSavingSchedule(true);
    setError("");
    try {
      const payload = {
        meeting_type: scheduleType,
        meeting_link: scheduleLink,
        meeting_at: toIsoDateTime(scheduleAt),
      };
      const response = await fetcher(`/admin/shariah-applications/${selectedId}/schedule`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      setSelected(data || null);
      setItems((prev) =>
        prev.map((item) => (item.id === data.id ? data : item)),
      );
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    } finally {
      setSavingSchedule(false);
    }
  };

  const toggleRole = (slug) => {
    setDecisionRoles((prev) => {
      if (prev.includes(slug)) {
        return prev.filter((role) => role !== slug);
      }
      if (prev.length >= 2) {
        return prev;
      }
      return [...prev, slug];
    });
  };

  const handleDecisionSubmit = async () => {
    if (!selectedId) return;
    setSavingDecision(true);
    setError("");
    try {
      const payload = {
        status: decisionStatus,
        comment: decisionComment,
      };
      if (decisionStatus === "approved") {
        payload.roles = decisionRoles;
      }
      const response = await fetcher(`/admin/shariah-applications/${selectedId}/decision`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      setSelected(data || null);
      setItems((prev) =>
        prev.map((item) => (item.id === data.id ? data : item)),
      );
      setDecisionComment("");
    } catch (err) {
      setError(err.message || t("errors.requestFailed"));
    } finally {
      setSavingDecision(false);
    }
  };

  const columns = useMemo(
    () => [
      { key: "id", title: t("shariah.columns.id"), width: "90px" },
      {
        key: "full_name",
        title: t("shariah.columns.fullName"),
        width: "220px",
        render: (row) => row.full_name || t("common.notAvailable"),
      },
      {
        key: "status",
        title: t("shariah.columns.status"),
        width: "180px",
        render: (row) => resolveShariahStatusLabel(t, row.status),
      },
      {
        key: "country",
        title: t("shariah.columns.country"),
        width: "160px",
        render: (row) => row.country || t("common.notAvailable"),
      },
      {
        key: "city",
        title: t("shariah.columns.city"),
        width: "160px",
        render: (row) => row.city || t("common.notAvailable"),
      },
      {
        key: "created_at",
        title: t("shariah.columns.created"),
        width: "200px",
        render: (row) =>
          row.created_at
            ? formatDateTime(row.created_at, language)
            : t("common.notAvailable"),
      },
    ],
    [language, t],
  );

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {error ? <Notice kind="error">{error}</Notice> : null}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "0.75rem",
          padding: "0.75rem",
          border: `1px solid ${COLORS.border}`,
          borderRadius: "12px",
          backgroundColor: "#f8fafc",
        }}
      >
        <strong style={{ marginRight: "0.5rem" }}>{t("shariah.title")}</strong>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {t("shariah.filters.status")}
          <input
            type="text"
            value={statusCsv}
            onChange={(e) => setStatusCsv(e.target.value)}
            placeholder="pending_intro,meeting_scheduled"
            style={{ padding: "0.4rem", borderRadius: "8px", minWidth: "240px" }}
          />
        </label>
        <button type="button" style={buttonStyle("ghost")} onClick={loadItems} disabled={loading}>
          {t("tasks.refresh")}
        </button>
      </div>
      {loading ? <div>{t("common.loading")}</div> : null}
      <Table
        columns={columns}
        rows={items}
        emptyText={t("shariah.listEmpty")}
        rowKey="id"
        onRowClick={(row) => {
          setSelectedId(row.id);
          setSelected(null);
          setDecisionComment("");
          setDecisionStatus("approved");
        }}
      />

      {selectedId ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={handleClose}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: "1.25rem 1.5rem",
              borderRadius: "12px",
              minWidth: "420px",
              maxWidth: "980px",
              width: "92vw",
              maxHeight: "92vh",
              overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>
                {t("shariah.detail.title")} № {selectedId}
              </h3>
              <button type="button" style={buttonStyle("ghost")} onClick={handleClose}>
                {t("tasks.close")}
              </button>
            </div>

            {selected ? (
              <div style={{ display: "grid", gap: "0.4rem", marginBottom: "1rem", color: COLORS.secondaryText }}>
                <div>
                  <strong>{t("shariah.detail.user")}:</strong> {renderUser(selected)}
                </div>
                <div>
                  <strong>{t("shariah.detail.phone")}:</strong>{" "}
                  {selected.user_phone || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.email")}:</strong>{" "}
                  {selected.user_email || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.fullName")}:</strong>{" "}
                  {selected.full_name || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.country")}:</strong>{" "}
                  {selected.country || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.city")}:</strong>{" "}
                  {selected.city || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.educationPlace")}:</strong>{" "}
                  {selected.education_place || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.educationCompleted")}:</strong>{" "}
                  {selected.education_completed ? t("common.yes") : t("common.no")}
                </div>
                <div>
                  <strong>{t("shariah.detail.educationDetails")}:</strong>{" "}
                  {selected.education_details || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.knowledgeAreas")}:</strong>{" "}
                  {(selected.knowledge_areas || []).length
                    ? (selected.knowledge_areas || [])
                        .map((area) => resolveShariahAreaLabel(t, area))
                        .join(", ")
                    : t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.experience")}:</strong>{" "}
                  {selected.experience || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.responsibility")}:</strong>{" "}
                  {selected.responsibility_accepted ? t("common.yes") : t("common.no")}
                </div>
                <div>
                  <strong>{t("shariah.detail.status")}:</strong>{" "}
                  {resolveShariahStatusLabel(t, selected.status)}
                </div>
                <div>
                  <strong>{t("shariah.detail.meetingType")}:</strong>{" "}
                  {selected.meeting_type
                    ? resolveLabel(t, "shariah.meetingTypes", selected.meeting_type)
                    : t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.meetingAt")}:</strong>{" "}
                  {selected.meeting_at
                    ? formatDateTime(selected.meeting_at, language)
                    : t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.meetingLink")}:</strong>{" "}
                  {selected.meeting_link || t("common.notAvailable")}
                </div>
                {selected.meeting_link ? (
                  <a href={selected.meeting_link} target="_blank" rel="noreferrer">
                    {selected.meeting_link}
                  </a>
                ) : null}
                <div>
                  <strong>{t("shariah.detail.decisionComment")}:</strong>{" "}
                  {selected.decision_comment || t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.assignedRoles")}:</strong>{" "}
                  {(selected.assigned_roles || []).length
                    ? (selected.assigned_roles || [])
                        .map((role) => resolveRoleLabel(t, role))
                        .join(", ")
                    : t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.created")}:</strong>{" "}
                  {selected.created_at
                    ? formatDateTime(selected.created_at, language)
                    : t("common.notAvailable")}
                </div>
                <div>
                  <strong>{t("shariah.detail.updated")}:</strong>{" "}
                  {selected.updated_at
                    ? formatDateTime(selected.updated_at, language)
                    : t("common.notAvailable")}
                </div>
              </div>
            ) : (
              <div style={{ marginBottom: "1rem", color: COLORS.secondaryText }}>
                {t("common.loading")}
              </div>
            )}

            {canManage ? (
              <>
                <div
                  style={{
                    padding: "0.75rem",
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: "10px",
                    backgroundColor: "#eef2ff",
                    display: "grid",
                    gap: "0.75rem",
                    marginBottom: "1rem",
                  }}
                >
                  <strong>{t("shariah.schedule.title")}</strong>
                  <label style={{ display: "grid", gap: "0.3rem" }}>
                    <span>{t("shariah.schedule.type")}</span>
                    <select
                      value={scheduleType}
                      onChange={(e) => setScheduleType(e.target.value)}
                      style={{ padding: "0.4rem", borderRadius: "8px" }}
                    >
                      {meetingOptions.map((type) => (
                        <option key={type} value={type}>
                          {resolveLabel(t, "shariah.meetingTypes", type)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label style={{ display: "grid", gap: "0.3rem" }}>
                    <span>{t("shariah.schedule.link")}</span>
                    <input
                      type="text"
                      value={scheduleLink}
                      onChange={(e) => setScheduleLink(e.target.value)}
                      style={{ padding: "0.4rem", borderRadius: "8px" }}
                    />
                  </label>
                  <label style={{ display: "grid", gap: "0.3rem" }}>
                    <span>{t("shariah.schedule.date")}</span>
                    <input
                      type="datetime-local"
                      value={scheduleAt}
                      onChange={(e) => setScheduleAt(e.target.value)}
                      style={{ padding: "0.4rem", borderRadius: "8px" }}
                    />
                  </label>
                  <button
                    type="button"
                    style={buttonStyle("primary")}
                    onClick={handleScheduleSubmit}
                    disabled={savingSchedule}
                  >
                    {t("shariah.schedule.submit")}
                  </button>
                </div>

                <div
                  style={{
                    padding: "0.75rem",
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: "10px",
                    backgroundColor: "#f8fafc",
                    display: "grid",
                    gap: "0.75rem",
                    marginBottom: "1rem",
                  }}
                >
                  <strong>{t("shariah.decision.title")}</strong>
                  <label style={{ display: "grid", gap: "0.3rem" }}>
                    <span>{t("shariah.decision.status")}</span>
                    <select
                      value={decisionStatus}
                      onChange={(e) => setDecisionStatus(e.target.value)}
                      style={{ padding: "0.4rem", borderRadius: "8px" }}
                    >
                      {decisionOptions.map((status) => (
                        <option key={status} value={status}>
                          {resolveShariahStatusLabel(t, status)}
                        </option>
                      ))}
                    </select>
                  </label>
                  {decisionStatus === "approved" ? (
                    <div style={{ display: "grid", gap: "0.4rem" }}>
                      <div style={{ fontWeight: 600 }}>{t("shariah.decision.roles")}</div>
                      <div style={{ color: COLORS.secondaryText, fontSize: "0.85rem" }}>
                        {t("shariah.decision.roleHint")}
                      </div>
                      <div style={{ display: "grid", gap: "0.35rem" }}>
                        {roleOptions.map((role) => {
                          const selectedRole = decisionRoles.includes(role);
                          const disabled =
                            !selectedRole && decisionRoles.length >= 2;
                          return (
                            <label key={role} style={{ display: "flex", gap: "0.5rem" }}>
                              <input
                                type="checkbox"
                                checked={selectedRole}
                                onChange={() => toggleRole(role)}
                                disabled={disabled}
                              />
                              {resolveRoleLabel(t, role)}
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}
                  <label style={{ display: "grid", gap: "0.3rem" }}>
                    <span>{t("shariah.decision.comment")}</span>
                    <textarea
                      rows={3}
                      value={decisionComment}
                      onChange={(e) => setDecisionComment(e.target.value)}
                      style={{
                        padding: "0.6rem",
                        borderRadius: "10px",
                        border: `1px solid ${COLORS.border}`,
                      }}
                    />
                  </label>
                  <button
                    type="button"
                    style={buttonStyle("primary")}
                    onClick={handleDecisionSubmit}
                    disabled={savingDecision}
                  >
                    {t("shariah.decision.submit")}
                  </button>
                </div>
              </>
            ) : null}

            <div style={{ display: "grid", gap: "0.5rem" }}>
              <h4 style={{ margin: 0 }}>{t("shariah.historyTitle")}</h4>
              <HistoryList items={selected?.history} t={t} language={language} />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

const ShariahControlTab = ({ fetcher, profile }) => {
  const { t } = useI18n();
  const roleSet = useMemo(() => new Set(profile?.roles || []), [profile?.roles]);
  const isOwner = roleSet.has("owner") || roleSet.has("superadmin");
  const canViewGoodDeeds =
    isOwner ||
    roleSet.has("tz_good_deeds") ||
    roleSet.has("shariah_chief") ||
    roleSet.has("shariah_observer");
  const canDecideGoodDeeds =
    isOwner || roleSet.has("tz_good_deeds") || roleSet.has("shariah_chief");
  const canManageApplications = isOwner || roleSet.has("shariah_chief");

  const tabs = useMemo(() => {
    const list = [];
    if (canViewGoodDeeds) {
      list.push({ key: "good_deeds", label: t("shariahControl.tabs.deeds") });
      list.push({ key: "needy", label: t("shariahControl.tabs.needy") });
      list.push({
        key: "confirmations",
        label: t("shariahControl.tabs.confirmations"),
      });
    }
    if (canManageApplications) {
      list.push({ key: "applications", label: t("shariahControl.tabs.applications") });
    }
    return list;
  }, [canManageApplications, canViewGoodDeeds, t]);

  const [activeTab, setActiveTab] = useState("");

  useEffect(() => {
    if (!tabs.length) return;
    const exists = tabs.some((tab) => tab.key === activeTab);
    if (!exists) {
      setActiveTab(tabs[0].key);
    }
  }, [activeTab, tabs]);

  if (!tabs.length) {
    return <Notice kind="info">{t("shariahControl.empty")}</Notice>;
  }

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            style={activeTab === tab.key ? buttonStyle("primary") : buttonStyle("ghost")}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {activeTab === "good_deeds" ? (
        <GoodDeedsTab fetcher={fetcher} canDecide={canDecideGoodDeeds} />
      ) : null}
      {activeTab === "needy" ? (
        <GoodDeedNeedyTab fetcher={fetcher} canDecide={canDecideGoodDeeds} />
      ) : null}
      {activeTab === "confirmations" ? (
        <GoodDeedConfirmationsTab fetcher={fetcher} canDecide={canDecideGoodDeeds} />
      ) : null}
      {activeTab === "applications" ? (
        <ShariahApplicationsTab fetcher={fetcher} canManage={canManageApplications} />
      ) : null}
    </div>
  );
};

const Dashboard = ({ token, profile, onLogout }) => {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState("userManagement");

  const tabs = useMemo(() => {
    const roleSet = new Set(profile?.roles || []);
    const config = [
      { key: "userManagement", label: t("tabs.userManagement"), required: ["admin_users"] },
      { key: "languages", label: t("tabs.languages"), required: ["admin_languages"] },
      { key: "links", label: t("tabs.links"), required: ["admin_links"] },
      { key: "blacklist", label: t("tabs.blacklist"), required: ["admin_blacklist"] },
      { key: "tasks", label: t("tabs.tasks"), required: ["admin_work_items_view"] },
      { key: "courts", label: t("tabs.courts"), required: ["admin_work_items_view", "tz_courts"] },
      { key: "contracts", label: t("tabs.contracts"), required: ["admin_work_items_view", "tz_contracts"] },
      { key: "documents", label: t("tabs.documents"), required: ["admin_documents"] },
      { key: "templates", label: t("tabs.templates"), required: ["admin_templates"] },
      {
        key: "shariahControl",
        label: t("tabs.shariahControl"),
        required: ["tz_good_deeds", "shariah_chief", "shariah_observer"],
      },
    ];
    return config
      .filter((tab) => {
        if (roleSet.has("owner") || roleSet.has("superadmin")) return true;
        if (tab.key === "courts") {
          return roleSet.has("admin_work_items_view") && roleSet.has("tz_courts");
        }
        if (tab.key === "contracts") {
          return roleSet.has("admin_work_items_view") && roleSet.has("tz_contracts");
        }
        return (tab.required || []).some((r) => roleSet.has(r));
      })
      .map(({ required, ...rest }) => rest);
  }, [profile?.roles, t]);

  useEffect(() => {
    if (!tabs.length) {
      return;
    }
    const exists = tabs.some((tab) => tab.key === activeTab);
    if (!exists) {
      setActiveTab(tabs[0].key);
    }
  }, [tabs, activeTab]);

  const fetcher = useCallback(
    async (path, options = {}) => {
      const { method = "GET", body, headers: customHeaders = {} } = options;
      const headers = {
        Authorization: `Bearer ${token}`,
        ...customHeaders,
      };
      const config = {
        method,
        headers,
      };
      if (body !== undefined) {
        config.body = body;
      }
      if (
        body !== undefined &&
        !(body instanceof FormData) &&
        !headers["Content-Type"]
      ) {
        headers["Content-Type"] = "application/json";
      }
      const response = await fetch(`${API_BASE_URL}${path}`, config);
      if (response.status === 401) {
        onLogout();
        throw new Error(t("errors.sessionExpired"));
      }
      if (!response.ok) {
        let detail;
        try {
          const payload = await response.json();
          const d = payload?.detail;
          if (typeof d === "string") {
            detail = d;
          } else if (Array.isArray(d)) {
            detail = d
              .map((i) => {
                const msg = i?.msg || i?.detail || JSON.stringify(i);
                const loc = Array.isArray(i?.loc) ? ` [${i.loc.join(".")}]` : "";
                return `${msg}${loc}`;
              })
              .join("; ");
          } else if (d) {
            detail = JSON.stringify(d);
          }
        } catch (err) {
          detail = undefined;
        }
        if (!detail) {
          try {
            detail = await response.text();
          } catch (_e) {
            detail = undefined;
          }
        }
        throw new Error(
          detail || t("errors.requestFailed", { status: response.status }),
        );
      }
      return response;
    },
    [token, onLogout, t],
  );

  let content = null;
  if (!tabs.length) {
    content = <Notice kind="error">{t("errors.forbidden")}</Notice>;
  } else if (activeTab === "userManagement") {
    content = <UserManagementTab fetcher={fetcher} profile={profile} />;
  } else if (activeTab === "languages") {
    content = <LanguagesTab fetcher={fetcher} />;
  } else if (activeTab === "links") {
    content = <LinksTab fetcher={fetcher} />;
  } else if (activeTab === "blacklist") {
    content = <BlacklistTab fetcher={fetcher} />;
  } else if (activeTab === "tasks") {
    content = <TasksTab fetcher={fetcher} profile={profile} />;
  } else if (activeTab === "courts") {
    content = <CourtCasesTab fetcher={fetcher} profile={profile} />;
  } else if (activeTab === "contracts") {
    content = <ContractsTab fetcher={fetcher} profile={profile} />;
  } else if (activeTab === "documents") {
    content = <DocumentsTab fetcher={fetcher} />;
  } else if (activeTab === "templates") {
    content = <ContractTemplatesTab fetcher={fetcher} />;
  } else if (activeTab === "shariahControl") {
    content = <ShariahControlTab fetcher={fetcher} profile={profile} />;
  } else {
    content = <DocumentsTab fetcher={fetcher} />;
  }

  return (
    <div style={LAYOUT.container}>
      <Card
        title={t("dashboard.welcome", { username: profile.username })}
        subtitle={t("dashboard.subtitle")}
        actions={<LanguageSwitcher />}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "1rem",
            marginBottom: "1.5rem",
          }}
        >
          <Tabs active={activeTab} onChange={setActiveTab} tabs={tabs} />
          <button
            type="button"
            style={buttonStyle("ghost")}
            onClick={onLogout}
          >
            {t("actions.logout")}
          </button>
        </div>
        {content}
      </Card>
    </div>
  );
};

const AdminApp = () => {
  const { t } = useI18n();
  const [token, setToken] = useState(() =>
    localStorage.getItem(TOKEN_STORAGE_KEY),
  );
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pendingToken, setPendingToken] = useState(null);
  const [loginUsername, setLoginUsername] = useState("");

  const handleLogout = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setProfile(null);
    setError("");
  }, []);

  useEffect(() => {
    if (!token) {
      setProfile(null);
      return;
    }
    let cancelled = false;
    const loadProfile = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/profile`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        });
        if (!response.ok) {
          throw new Error();
        }
        const data = await response.json();
        if (!cancelled) {
          setProfile(data);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          handleLogout();
          setError(t("errors.sessionExpired"));
        }
      }
    };
    loadProfile();
    return () => {
      cancelled = true;
    };
  }, [token, handleLogout, t]);

  const handleLogin = async (username, password) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || t("login.error"));
      }
      const data = await response.json();
      setPendingToken(data.pending_token);
      setLoginUsername(username);
      setError("");
    } catch (err) {
      setError(err.message || t("login.error"));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (code) => {
    if (!pendingToken) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pending_token: pendingToken, code }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || t("login.error"));
      }
      const data = await response.json();
      localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
      setToken(data.access_token);
      setPendingToken(null);
      setError("");
    } catch (err) {
      setError(err.message || t("login.error"));
    } finally {
      setLoading(false);
    }
  };

  if (!token || !profile) {
    return (
      <div style={LAYOUT.container}>
        {pendingToken ? (
          <OtpForm
            onSubmit={handleVerifyOtp}
            onBack={() => {
              setPendingToken(null);
              setError("");
            }}
            loading={loading}
            error={error}
            username={loginUsername}
          />
        ) : (
          <LoginForm onSubmit={handleLogin} loading={loading} error={error} />
        )}
      </div>
    );
  }

  return <Dashboard token={token} profile={profile} onLogout={handleLogout} />;
};

const Root = () => {
  const [uiLanguage, setUiLanguage] = useState(() => {
    const stored = localStorage.getItem(UI_LANGUAGE_STORAGE_KEY);
    return SUPPORTED_UI_LANGUAGES.includes(stored) ? stored : "ru";
  });

  const handleChangeLanguage = useCallback((code) => {
    setUiLanguage(code);
    localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, code);
  }, []);

  return (
    <TranslationProvider
      language={uiLanguage}
      onChangeLanguage={handleChangeLanguage}
    >
      <AdminApp />
    </TranslationProvider>
  );
};

const container = document.getElementById("root");
createRoot(container).render(<Root />);












