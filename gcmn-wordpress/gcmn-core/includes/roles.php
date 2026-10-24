<?php
defined( 'ABSPATH' ) || exit;

/**
 * Roles from the Website Implementation System:
 *  Content Owner (strategy or department)  writes and submits, cannot publish
 *  Content Editor (Communications)         reviews and edits everyone's work, cannot publish
 *  Website Administrator                   publishes approved content
 * Site administrators get the same extra capabilities.
 */
function gcmn_add_roles() {
	$owner = array( 'read' => true, 'edit_posts' => true, 'delete_posts' => true, 'upload_files' => true, 'gcmn_submit_content' => true );
	$editor = $owner + array(
		'edit_others_posts' => true, 'edit_pages' => true, 'edit_others_pages' => true, 'edit_private_posts' => true, 'edit_private_pages' => true,
		'read_private_posts' => true, 'read_private_pages' => true, 'gcmn_view_tracker' => true,
	);
	$publisher = $editor + array(
		'publish_posts' => true, 'publish_pages' => true, 'edit_published_posts' => true, 'edit_published_pages' => true,
		'delete_published_posts' => true, 'delete_others_posts' => true, 'delete_pages' => true, 'delete_published_pages' => true, 'delete_others_pages' => true,
		'manage_categories' => true, 'gcmn_manage_enquiries' => true, 'gcmn_send_owner_emails' => true,
	);
	remove_role( 'gcmn_content_owner' );
	remove_role( 'gcmn_content_editor' );
	remove_role( 'gcmn_publisher' );
	add_role( 'gcmn_content_owner', 'Content Owner', $owner );
	add_role( 'gcmn_content_editor', 'Content Editor', $editor );
	add_role( 'gcmn_publisher', 'Website Administrator', $publisher );
	$admin = get_role( 'administrator' );
	if ( $admin ) {
		foreach ( array( 'gcmn_submit_content', 'gcmn_view_tracker', 'gcmn_manage_enquiries', 'gcmn_send_owner_emails' ) as $cap ) {
			$admin->add_cap( $cap );
		}
	}
}

/** Keep roles in step with the plugin version without needing a re-activation. */
add_action( 'init', function () {
	if ( get_option( 'gcmn_roles_version' ) !== GCMN_VERSION ) {
		gcmn_add_roles();
		update_option( 'gcmn_roles_version', GCMN_VERSION );
	}
}, 5 );
