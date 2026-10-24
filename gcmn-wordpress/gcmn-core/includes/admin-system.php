<?php
defined( 'ABSPATH' ) || exit;

/**
 * The "Website system" menu: one place for the Website Implementation System screens.
 * The Owner emails entry shows a count of messages waiting for the Website Administrator.
 */
add_action( 'admin_menu', function () {
	if ( ! current_user_can( 'gcmn_view_tracker' ) ) {
		return;
	}
	$waiting = current_user_can( 'gcmn_send_owner_emails' ) ? gcmn_outbox_count() : 0;
	$bubble  = $waiting ? ' <span class="awaiting-mod">' . (int) $waiting . '</span>' : '';
	add_menu_page( 'Website system', 'Website system' . $bubble, 'gcmn_view_tracker', 'gcmn-tracker', 'gcmn_render_tracker', 'dashicons-networking', 26 );
	add_submenu_page( 'gcmn-tracker', 'Content tracker', 'Content tracker', 'gcmn_view_tracker', 'gcmn-tracker', 'gcmn_render_tracker' );
	if ( current_user_can( 'gcmn_send_owner_emails' ) ) {
		add_submenu_page( 'gcmn-tracker', 'Owner emails', 'Owner emails' . $bubble, 'gcmn_send_owner_emails', 'gcmn-owner-emails', 'gcmn_render_outbox' );
	}
	add_submenu_page( 'gcmn-tracker', 'Website audit', 'Website audit', 'gcmn_view_tracker', 'gcmn-audit', 'gcmn_render_audit' );
	add_submenu_page( 'gcmn-tracker', 'Monthly review', 'Monthly review', 'gcmn_view_tracker', 'gcmn-review', 'gcmn_render_review' );
	add_submenu_page( 'gcmn-tracker', 'Measures of success', 'Measures', 'gcmn_view_tracker', 'gcmn-measures', 'gcmn_render_measures' );
	add_submenu_page( 'gcmn-tracker', 'Training', 'Training', 'gcmn_view_tracker', 'gcmn-training', 'gcmn_render_training' );
	add_submenu_page( 'gcmn-tracker', '90-day plan', '90-day plan', 'gcmn_view_tracker', 'gcmn-plan', 'gcmn_render_plan' );
	add_submenu_page( 'gcmn-tracker', 'Who owns what', 'Who owns what', 'gcmn_view_tracker', 'gcmn-ownership', 'gcmn_render_ownership' );
} );
