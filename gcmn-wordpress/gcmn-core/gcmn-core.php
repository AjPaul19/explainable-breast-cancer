<?php
/**
 * Plugin Name:       GCMN Core
 * Description:       Content types, submission and review workflow, enquiries, giving details and content import for the Great Commission Movement, Nigeria website. Works with the GCMN theme.
 * Version:           1.2.0
 * Requires at least: 6.4
 * Requires PHP:      7.4
 * Author:            Great Commission Movement, Nigeria
 * License:           GPL-2.0-or-later
 * Text Domain:       gcmn
 */

defined( 'ABSPATH' ) || exit;

define( 'GCMN_VERSION', '1.2.0' );
define( 'GCMN_DIR', plugin_dir_path( __FILE__ ) );
define( 'GCMN_URL', plugin_dir_url( __FILE__ ) );

foreach ( array( 'helpers', 'settings', 'content-types', 'roles', 'workflow', 'submission', 'enquiries', 'freshness', 'outbox', 'audit', 'review', 'measures', 'admin-system', 'blocks', 'elementor', 'parts', 'redirects', 'importer', 'seo' ) as $gcmn_file ) {
	require_once GCMN_DIR . 'includes/' . $gcmn_file . '.php';
}

register_activation_hook( __FILE__, 'gcmn_activate' );
register_deactivation_hook( __FILE__, 'gcmn_deactivate' );

/**
 * Activation: register everything once so permalinks work, add roles, create the functional pages the plugin needs
 * (home, news, contact, submit content) and schedule the daily freshness check. Content pages come from the importer.
 */
function gcmn_activate() {
	gcmn_register_content_types();
	gcmn_add_roles();
	gcmn_ensure_functional_pages();
	// The website's real content ships inside the plugin and loads from the dashboard, in small steps with a progress bar.
	if ( ! wp_next_scheduled( 'gcmn_daily' ) ) {
		wp_schedule_event( time() + HOUR_IN_SECONDS, 'daily', 'gcmn_daily' );
	}
	flush_rewrite_rules();
}

function gcmn_deactivate() {
	wp_clear_scheduled_hook( 'gcmn_daily' );
	flush_rewrite_rules();
}
