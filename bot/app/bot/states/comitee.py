from aiogram.fsm.state import State, StatesGroup


class ScholarAnswers(StatesGroup):
    answer = State()


class ContractCreation(StatesGroup):
    waiting_for_name = State()
    waiting_for_file = State()


class ContractSearch(StatesGroup):
    waiting_for_search_query = State()


class ContractTemplateFlow(StatesGroup):
    waiting_for_field = State()
    preview = State()
    waiting_for_recipient = State()


class ContractAgreementFlow(StatesGroup):
    waiting_for_comment = State()


class ContractAutoPickFlow(StatesGroup):
    waiting_for_answer = State()
    waiting_for_confirm = State()


class BlacklistSearchFlow(StatesGroup):
    waiting_for_query = State()


class BlacklistComplaintFlow(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_birthdate = State()
    waiting_for_city = State()
    waiting_for_reason = State()
    waiting_for_media = State()


class BlacklistAppealFlow(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_birthdate = State()
    waiting_for_city = State()
    waiting_for_reason = State()
    waiting_for_media = State()


class CourtClaimFlow(StatesGroup):
    choosing_category = State()
    waiting_for_plaintiff = State()
    waiting_for_defendant = State()
    waiting_for_claim = State()
    waiting_for_amount = State()
    waiting_for_contract_question = State()
    waiting_for_contract_file = State()
    waiting_for_family_relation = State()
    waiting_for_evidence = State()
    waiting_for_confirm = State()


class CourtCaseEditFlow(StatesGroup):
    waiting_for_claim = State()
    waiting_for_category = State()
    waiting_for_evidence = State()


class CourtCaseMediateFlow(StatesGroup):
    active = State()


class InheritanceCalcFlow(StatesGroup):
    waiting_for_mode = State()
    waiting_for_non_muslim = State()
    waiting_for_deceased_gender = State()
    waiting_for_spouse = State()
    waiting_for_sons = State()
    waiting_for_daughters = State()
    waiting_for_father_alive = State()
    waiting_for_mother_alive = State()
    waiting_for_brothers = State()
    waiting_for_sisters = State()
    waiting_for_estate_amount = State()
    waiting_for_debts_amount = State()


class InheritanceGuardianFlow(StatesGroup):
    waiting_for_guardian_name = State()
    waiting_for_reason = State()
    waiting_for_scope = State()
    waiting_for_contact = State()


class InheritanceAskFlow(StatesGroup):
    waiting_for_request_type = State()
    waiting_for_text_question = State()
    waiting_for_video_time = State()
    waiting_for_video_contact = State()
    waiting_for_video_description = State()
    waiting_for_attachments = State()
    waiting_for_attachments_description = State()


class InheritanceWasiyaFlow(StatesGroup):
    waiting_for_estate_amount = State()
    waiting_for_wasiya_amount = State()


class NikahNewFlow(StatesGroup):
    waiting_for_role = State()

    waiting_for_groom_name = State()
    waiting_for_groom_age = State()
    waiting_for_groom_is_muslim = State()
    waiting_for_groom_contact = State()

    waiting_for_bride_name = State()
    waiting_for_bride_age = State()
    waiting_for_bride_is_muslim = State()
    waiting_for_bride_contact = State()

    waiting_for_wali_presence = State()
    waiting_for_wali_name = State()
    waiting_for_wali_contact = State()
    waiting_for_wali_relation = State()
    waiting_for_wali_is_muslim = State()
    waiting_for_wali_approves = State()

    waiting_for_witness_1_name = State()
    waiting_for_witness_1_contact = State()
    waiting_for_witness_1_is_muslim = State()
    waiting_for_witness_2_name = State()
    waiting_for_witness_2_contact = State()
    waiting_for_witness_2_is_muslim = State()

    waiting_for_mahr_description = State()
    waiting_for_mahr_payment_mode = State()
    waiting_for_mahr_payment_terms = State()

    waiting_for_obstacle_iddah = State()
    waiting_for_obstacle_mahram = State()
    waiting_for_obstacle_third_marriage = State()
    waiting_for_obstacle_prior_without_wali = State()

    waiting_for_ijabqabul_confirm = State()


class NikahAskFlow(StatesGroup):
    waiting_for_request_type = State()
    waiting_for_text_question = State()
    waiting_for_video_time = State()
    waiting_for_video_contact = State()
    waiting_for_video_description = State()
    waiting_for_attachments = State()
    waiting_for_attachments_description = State()


class SpouseProfileFlow(StatesGroup):
    waiting_for_gender = State()
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_location = State()
    waiting_for_marital_status = State()
    waiting_for_wali_presence = State()
    waiting_for_requirements = State()
    waiting_for_relocation = State()
    waiting_for_wali_contact = State()
    waiting_for_publish = State()


class SpouseSearchFlow(StatesGroup):
    waiting_for_country = State()
    waiting_for_age_range = State()
    waiting_for_marital_status = State()
    waiting_for_prayer = State()
    waiting_for_relocation = State()
    showing_results = State()


class SpouseWaliLinkFlow(StatesGroup):
    waiting_for_code = State()


class SpouseConversationFlow(StatesGroup):
    active = State()


class SpouseAskFlow(StatesGroup):
    waiting_for_request_type = State()
    waiting_for_text_question = State()
    waiting_for_video_time = State()
    waiting_for_video_contact = State()
    waiting_for_video_description = State()
    waiting_for_attachments = State()
    waiting_for_attachments_description = State()


class ProposalCreateFlow(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_goal = State()
    waiting_for_shariah_basis = State()
    waiting_for_shariah_text = State()
    waiting_for_conditions = State()
    waiting_for_terms = State()
    waiting_for_confirm = State()


class ProposalReviewFlow(StatesGroup):
    waiting_for_revision_comment = State()
    waiting_for_rejection_reason = State()


class ExecutionReportFlow(StatesGroup):
    waiting_for_comment = State()
    waiting_for_proof = State()


class ExecutionReviewFlow(StatesGroup):
    waiting_for_reject_reason = State()


class GoodDeedCreateFlow(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_city = State()
    waiting_for_country = State()
    waiting_for_help_type = State()
    waiting_for_amount = State()
    waiting_for_comment = State()
    waiting_for_confirm = State()


class GoodDeedNeedyFlow(StatesGroup):
    waiting_for_person_type = State()
    waiting_for_city = State()
    waiting_for_country = State()
    waiting_for_reason = State()
    waiting_for_zakat = State()
    waiting_for_fitr = State()
    waiting_for_comment = State()
    waiting_for_confirm = State()


class GoodDeedLocationFilterFlow(StatesGroup):
    waiting_for_query = State()


class GoodDeedConfirmationFlow(StatesGroup):
    waiting_for_text = State()
    waiting_for_attachment = State()


class GoodDeedClarifyFlow(StatesGroup):
    waiting_for_text = State()
    waiting_for_attachment = State()


class ShariahAdminApplicationFlow(StatesGroup):
    waiting_for_name = State()
    waiting_for_country = State()
    waiting_for_country_custom = State()
    waiting_for_city = State()
    waiting_for_education_place = State()
    waiting_for_education_completed = State()
    waiting_for_education_details = State()
    waiting_for_knowledge_areas = State()
    waiting_for_experience = State()
    waiting_for_responsibility = State()
