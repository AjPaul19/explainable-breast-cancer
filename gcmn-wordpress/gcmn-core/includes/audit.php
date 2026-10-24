<?php
defined( 'ABSPATH' ) || exit;

/**
 * Website audit and improvement system (Website Implementation System, section 8).
 * Every priority area is classified as CURRENT, NEEDS UPDATING, NEEDS REPLACEMENT OR REMOVAL, or MISSING.
 */
function gcmn_audit_statuses() {
	return array(
		'current'  => 'Current: accurate, relevant and useful',
		'updating' => 'Needs updating: outdated or incomplete',
		'replace'  => 'Needs replacement or removal: no longer relevant',
		'missing'  => 'Missing: important information that should exist is not there',
	);
}

/** The ten priority areas, where each lives on the site, and the department that normally owns it (from the ownership matrix). */
function gcmn_audit_areas() {
	return array(
		'who'       => array( 'Who we are, mission and vision', array( 'page', 'who-we-are' ), 'Leadership' ),
		'history'   => array( 'GCMN history', array( 'page', 'our-history' ), 'Leadership' ),
		'strategies' => array( 'Strategies and ministries', array( 'archive', 'gcmn_strategy' ), '' ),
		'contact'   => array( 'Contact information', array( 'page', 'contact' ), 'Operations' ),
		'partner'   => array( 'Partnership opportunities', array( 'page', 'partnership' ), 'Funding and Resource Mobilisation Team' ),
		'giving'    => array( 'Giving information', array( 'page', 'giving' ), 'Finance' ),
		'serve'     => array( 'Serve and join staff', array( 'page', 'serve' ), 'LDHR' ),
		'stories'   => array( 'Stories and testimonies', array( 'archive', 'gcmn_story' ), '' ),
		'prayer'    => array( 'Prayer opportunities', array( 'archive', 'gcmn_prayer' ), 'Funding and Resource Mobilisation Team' ),
		'resources' => array( 'Resources', array( 'archive', 'gcmn_resource' ), '' ),
	);
}

function gcmn_audit_url( $where ) {
	if ( 'page' === $where[0] ) {
		$pg = get_page_by_path( $where[1] );
		return $pg ? get_permalink( $pg ) : '';
	}
	return get_post_type_archive_link( $where[1] ) ?: '';
}

function gcmn_audit_data() {
	$d = get_option( 'gcmn_audit', array() );
	return is_array( $d ) ? $d : array();
}

/** Share of the ten priority areas currently classified as Current, and how many have been audited. */
function gcmn_audit_summary() {
	$d      = gcmn_audit_data();
	$counts = array( 'current' => 0, 'updating' => 0, 'replace' => 0, 'missing' => 0 );
	foreach ( gcmn_audit_areas() as $k => $a ) {
		if ( isset( $d[ $k ]['status'] ) && isset( $counts[ $d[ $k ]['status'] ] ) ) {
			$counts[ $d[ $k ]['status'] ]++;
		}
	}
	$done = array_sum( $counts );
	return array( 'counts' => $counts, 'audited' => $done, 'total' => count( gcmn_audit_areas() ), 'percent_current' => $done ? (int) round( 100 * $counts['current'] / count( gcmn_audit_areas() ) ) : 0 );
}

function gcmn_render_audit() {
	if ( ! current_user_can( 'gcmn_view_tracker' ) ) {
		wp_die( 'Not allowed.' );
	}
	$d    = gcmn_audit_data();
	$sum  = gcmn_audit_summary();
	$stat = gcmn_audit_statuses();
	echo '<div class="wrap"><h1>Website audit</h1><p>Before regular updates begin, classify each priority area. Come back to it whenever you review the site.</p>';
	if ( isset( $_GET['gcmn_msg'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
		echo '<div class="notice notice-success is-dismissible"><p>' . esc_html( rawurldecode( sanitize_text_field( wp_unslash( $_GET['gcmn_msg'] ) ) ) ) . '</p></div>'; // phpcs:ignore WordPress.Security.NonceVerification
	}
	echo '<p><strong>' . (int) $sum['audited'] . ' of ' . (int) $sum['total'] . ' areas audited.</strong> Current: ' . (int) $sum['counts']['current'] . ' · Needs updating: ' . (int) $sum['counts']['updating'] . ' · Needs replacement or removal: ' . (int) $sum['counts']['replace'] . ' · Missing: ' . (int) $sum['counts']['missing'] . '</p>';
	echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '">';
	wp_nonce_field( 'gcmn_audit', 'gcmn_audit_nonce' );
	echo '<input type="hidden" name="action" value="gcmn_audit"><table class="widefat striped"><thead><tr><th>Priority area</th><th>Where it is</th><th>Classification</th><th>Note</th><th>Prepare an email to the owner</th></tr></thead><tbody>';
	$depts = array_keys( gcmn_departments() );
	foreach ( gcmn_audit_areas() as $k => $a ) {
		$row = isset( $d[ $k ] ) ? $d[ $k ] : array();
		$url = gcmn_audit_url( $a[1] );
		echo '<tr><td><strong>' . esc_html( $a[0] ) . '</strong>' . ( ! empty( $row['date'] ) ? '<br><span class="description">Audited ' . esc_html( gcmn_date( $row['date'] ) ) . '</span>' : '' ) . '</td>';
		echo '<td>' . ( $url ? '<a href="' . esc_url( $url ) . '" target="_blank" rel="noopener">View</a>' : '<em>Not on the site</em>' ) . '</td>';
		echo '<td><select name="audit[' . esc_attr( $k ) . '][status]"><option value="">Not audited</option>';
		foreach ( $stat as $sk => $label ) {
			echo '<option value="' . esc_attr( $sk ) . '" ' . selected( isset( $row['status'] ) ? $row['status'] : '', $sk, false ) . '>' . esc_html( $label ) . '</option>';
		}
		echo '</select></td><td><input type="text" class="regular-text" name="audit[' . esc_attr( $k ) . '][note]" value="' . esc_attr( isset( $row['note'] ) ? $row['note'] : '' ) . '"></td>';
		echo '<td><select name="audit[' . esc_attr( $k ) . '][dept]"><option value="">Choose the owner</option>';
		foreach ( $depts as $dept ) {
			echo '<option ' . selected( $a[2], $dept, false ) . '>' . esc_html( $dept ) . '</option>';
		}
		echo '</select><br><label><input type="checkbox" name="audit[' . esc_attr( $k ) . '][ask]" value="1"> Prepare it</label></td></tr>';
	}
	echo '</tbody></table><p class="description">An email is only prepared, for areas that are not Current. It waits in Owner emails until the Website Administrator sends it.</p>';
	submit_button( 'Save the audit' );
	echo '</form></div>';
}

add_action( 'admin_post_gcmn_audit', function () {
	if ( ! current_user_can( 'gcmn_view_tracker' ) || ! isset( $_POST['gcmn_audit_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_audit_nonce'] ) ), 'gcmn_audit' ) ) {
		wp_die( 'Not allowed.', 403 );
	}
	$in    = isset( $_POST['audit'] ) && is_array( $_POST['audit'] ) ? wp_unslash( $_POST['audit'] ) : array();
	$old   = gcmn_audit_data();
	$new   = array();
	$stat  = gcmn_audit_statuses();
	$queued = 0;
	foreach ( gcmn_audit_areas() as $k => $a ) {
		$r      = isset( $in[ $k ] ) && is_array( $in[ $k ] ) ? $in[ $k ] : array();
		$status = isset( $r['status'] ) && isset( $stat[ $r['status'] ] ) ? $r['status'] : '';
		$note   = isset( $r['note'] ) ? sanitize_text_field( $r['note'] ) : '';
		$prev   = isset( $old[ $k ] ) ? $old[ $k ] : array();
		$date   = ( $status && ( ! isset( $prev['status'] ) || $prev['status'] !== $status ) ) ? gmdate( 'Y-m-d' ) : ( isset( $prev['date'] ) ? $prev['date'] : '' );
		$new[ $k ] = array( 'status' => $status, 'note' => $note, 'date' => $status ? $date : '' );
		if ( ! empty( $r['ask'] ) && $status && 'current' !== $status ) {
			$dept = isset( $r['dept'] ) ? sanitize_text_field( $r['dept'] ) : '';
			$url  = gcmn_audit_url( $a[1] );
			$id   = gcmn_outbox_add( array(
				'to'      => $dept ? gcmn_dept_emails( $dept )['owner'] : '',
				'dept'    => $dept,
				'reason'  => 'audit',
				'key'     => 'audit:' . $k . ':' . $status . ':' . md5( $note ),
				'subject' => 'Website audit: ' . $a[0] . ' (' . strtolower( strtok( $stat[ $status ], ':' ) ) . ')',
				'body'    => "Hello,\n\nThe website audit has classified “{$a[0]}” as " . strtolower( $stat[ $status ] ) . ".\n" . ( $note ? "\nNote: {$note}\n" : '' ) . ( $url ? "\nThe page: {$url}\n" : '' ) . "\nPlease send the Content Editor the updated information, using the Website Content Submission Form.\n",
			) );
			if ( $id ) {
				$queued++;
			}
		}
	}
	update_option( 'gcmn_audit', $new );
	if ( $queued ) {
		gcmn_outbox_alert_admin( $queued );
	}
	$msg = 'Audit saved.' . ( $queued ? " {$queued} email" . ( 1 === $queued ? '' : 's' ) . ' prepared for the Website Administrator to send.' : '' );
	wp_safe_redirect( add_query_arg( array( 'page' => 'gcmn-audit', 'gcmn_msg' => rawurlencode( $msg ) ), admin_url( 'admin.php' ) ) );
	exit;
} );
