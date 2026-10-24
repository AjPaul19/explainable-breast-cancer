<?php
defined( 'ABSPATH' ) || exit;

/**
 * Website Implementation System: measures of success (section 12), training (section 9),
 * the 90-day plan (section 11) and the ownership matrix (section 6).
 * Counts are read from the site itself. Nothing here sends an email.
 */

/* ---- training ---- */
function gcmn_training_skills() {
	return array(
		'structure' => 'Understand the website structure and CMS',
		'access'    => 'Log in and manage authorised access',
		'pages'     => 'Create and edit pages',
		'news'      => 'Create and publish news and stories',
		'media'     => 'Upload and manage images and videos',
		'events'    => 'Add and update events and resources',
		'links'     => 'Manage links and contact information',
		'preview'   => 'Preview content, including mobile presentation',
		'publish'   => 'Publish and unpublish approved content',
		'security'  => 'Follow security, approval and backup procedures',
		'approval'  => 'Know which changes need extra approval',
	);
}

function gcmn_training_data() {
	$d = get_option( 'gcmn_training', array() );
	return is_array( $d ) ? $d : array();
}

/** Staff counted as trained: every one of the skills ticked. */
function gcmn_trained_count() {
	$n = 0;
	foreach ( gcmn_training_data() as $p ) {
		if ( ! empty( $p['name'] ) && count( array_filter( (array) ( isset( $p['skills'] ) ? $p['skills'] : array() ) ) ) >= count( gcmn_training_skills() ) ) {
			$n++;
		}
	}
	return $n;
}

/* ---- 90-day plan ---- */
function gcmn_plan_phases() {
	return array(
		array( 'Days 1 to 30', 'Establish', array( 'Meet the technical team', 'Audit the website', 'Name the Content Owners, Editor and Administrators', 'Set up the approval process', 'Create the submission form and content tracker' ) ),
		array( 'Days 31 to 60', 'Build', array( 'Train the administrators', 'Update the priority pages', 'Establish regular submissions', 'Publish first stories, strategy updates and partnership information' ) ),
		array( 'Days 61 to 90', 'Test and improve', array( 'Operate the system', 'Find bottlenecks', 'Review submission and publication speed', 'Check website quality and track enquiries', 'Refine responsibilities and workflow' ) ),
	);
}

/* ---- ownership matrix ---- */
function gcmn_ownership_matrix() {
	return array(
		array( 'About and history', 'Leadership / assigned team', 'Communications', 'Website Administrator' ),
		array( 'Strategies', 'Each strategy', 'Communications', 'Website Administrator' ),
		array( 'News and stories', 'Strategies', 'Communications', 'Website Administrator' ),
		array( 'Testimonies', 'Strategies', 'Communications', 'Website Administrator' ),
		array( 'Resources', 'Relevant strategy', 'Communications', 'Website Administrator' ),
		array( 'Prayer', 'Funding and Resource Mobilisation Team / strategies', 'Communications', 'Website Administrator' ),
		array( 'Partnership', 'Funding and Resource Mobilisation Team', 'Communications', 'Website Administrator' ),
		array( 'Giving', 'Funding and Resource Mobilisation Team / Finance', 'Relevant leadership', 'Website Administrator' ),
	);
}

/* ---- measures ---- */
function gcmn_measures() {
	$since   = gmdate( 'Y-m-d', strtotime( '-90 days' ) );
	$count   = function ( $args ) {
		$q = new WP_Query( array_merge( array( 'posts_per_page' => 1, 'fields' => 'ids', 'no_found_rows' => false, 'gcmn_all' => true ), $args ) );
		return (int) $q->found_posts;
	};
	$owners = 0;
	foreach ( get_posts( array( 'post_type' => 'gcmn_strategy', 'post_status' => 'publish', 'numberposts' => 200, 'gcmn_all' => true ) ) as $s ) {
		if ( gcmn_dept_emails( $s->post_title )['owner'] ) {
			$owners++;
		}
	}
	$types     = gcmn_workflow_types();
	$modified  = array( array( 'column' => 'post_modified', 'after' => $since ) );
	$audit     = gcmn_audit_summary();
	$partner   = $count( array( 'post_type' => 'gcmn_enquiry', 'post_status' => 'any', 'meta_query' => array( array( 'key' => '_gcmn_topic', 'value' => 'partnership' ) ) ) );
	return array(
		array( 'Strategies with a named Content Owner', $owners, 'of ' . $count( array( 'post_type' => 'gcmn_strategy', 'post_status' => 'publish' ) ) ),
		array( 'Staff fully trained to update the website', gcmn_trained_count(), 'in the training tracker' ),
		array( 'Content submissions received through the form', $count( array( 'post_type' => $types, 'post_status' => 'any', 'meta_query' => array( array( 'key' => '_gcmn_via_form', 'value' => '1' ) ) ) ), 'all time' ),
		array( 'Approved items published', $count( array( 'post_type' => $types, 'post_status' => 'publish' ) ), 'all time' ),
		array( 'Strategy pages updated', $count( array( 'post_type' => 'gcmn_strategy', 'post_status' => 'publish', 'date_query' => $modified ) ), 'in the last 90 days' ),
		array( 'Stories and testimonies published', $count( array( 'post_type' => 'gcmn_story', 'post_status' => 'publish' ) ), 'all time' ),
		array( 'Resources and events updated', $count( array( 'post_type' => array( 'gcmn_resource', 'gcmn_event' ), 'post_status' => 'publish', 'date_query' => $modified ) ), 'in the last 90 days' ),
		array( 'Priority pages that are current', $audit['audited'] ? $audit['percent_current'] . '%' : 'Not audited yet', $audit['audited'] . ' of ' . $audit['total'] . ' areas audited' ),
		array( 'Website enquiries', $count( array( 'post_type' => 'gcmn_enquiry', 'post_status' => 'any' ) ), $partner . ' about partnership' ),
		array( 'Monthly reviews completed', count( gcmn_reviews() ), 'all time' ),
	);
}

function gcmn_render_measures() {
	if ( ! current_user_can( 'gcmn_view_tracker' ) ) {
		wp_die( 'Not allowed.' );
	}
	echo '<div class="wrap"><h1>Measures of success</h1><p>Read from the website each time this page opens.</p><table class="widefat striped" style="max-width:760px"><thead><tr><th>Measure</th><th>Now</th><th></th></tr></thead><tbody>';
	foreach ( gcmn_measures() as $m ) {
		echo '<tr><td>' . esc_html( $m[0] ) . '</td><td><strong>' . esc_html( $m[1] ) . '</strong></td><td class="description">' . esc_html( $m[2] ) . '</td></tr>';
	}
	echo '</tbody></table></div>';
}

function gcmn_render_ownership() {
	if ( ! current_user_can( 'gcmn_view_tracker' ) ) {
		wp_die( 'Not allowed.' );
	}
	echo '<div class="wrap"><h1>Who owns what</h1><table class="widefat striped" style="max-width:900px"><thead><tr><th>Website section</th><th>Content Owner</th><th>Editor / Reviewer</th><th>Publisher</th></tr></thead><tbody>';
	foreach ( gcmn_ownership_matrix() as $r ) {
		echo '<tr><td><strong>' . esc_html( $r[0] ) . '</strong></td><td>' . esc_html( $r[1] ) . '</td><td>' . esc_html( $r[2] ) . '</td><td>' . esc_html( $r[3] ) . '</td></tr>';
	}
	echo '</tbody></table><p class="description">Names and emails are set under Settings &gt; GCMN site &gt; People and emails.</p></div>';
}

function gcmn_render_training() {
	if ( ! current_user_can( 'gcmn_view_tracker' ) ) {
		wp_die( 'Not allowed.' );
	}
	$people = gcmn_training_data();
	for ( $i = 0; $i < 3; $i++ ) {
		$people[] = array( 'name' => '', 'email' => '', 'skills' => array() );
	}
	$skills = gcmn_training_skills();
	echo '<div class="wrap"><h1>Training</h1><p>Identified staff should be able to do the agreed updates on their own. Tick each skill once it has been shown to the person. Someone with every skill ticked counts as trained.</p>';
	if ( isset( $_GET['gcmn_msg'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
		echo '<div class="notice notice-success is-dismissible"><p>' . esc_html( rawurldecode( sanitize_text_field( wp_unslash( $_GET['gcmn_msg'] ) ) ) ) . '</p></div>'; // phpcs:ignore WordPress.Security.NonceVerification
	}
	echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '">';
	wp_nonce_field( 'gcmn_training', 'gcmn_training_nonce' );
	echo '<input type="hidden" name="action" value="gcmn_training"><div style="overflow:auto"><table class="widefat striped"><thead><tr><th>Name</th><th>Email</th>';
	foreach ( $skills as $label ) {
		echo '<th style="font-weight:400;font-size:11px;min-width:80px">' . esc_html( $label ) . '</th>';
	}
	echo '</tr></thead><tbody>';
	foreach ( array_values( $people ) as $i => $p ) {
		echo '<tr><td><input type="text" name="t[' . (int) $i . '][name]" value="' . esc_attr( $p['name'] ) . '"></td><td><input type="email" name="t[' . (int) $i . '][email]" value="' . esc_attr( $p['email'] ) . '"></td>';
		foreach ( $skills as $k => $label ) {
			echo '<td style="text-align:center"><input type="checkbox" name="t[' . (int) $i . '][skills][' . esc_attr( $k ) . ']" value="1" ' . checked( ! empty( $p['skills'][ $k ] ), true, false ) . ' aria-label="' . esc_attr( $label ) . '"></td>';
		}
		echo '</tr>';
	}
	echo '</tbody></table></div><p class="description">' . (int) gcmn_trained_count() . ' fully trained. Clear a name to remove the row.</p>';
	submit_button( 'Save training' );
	echo '</form></div>';
}

add_action( 'admin_post_gcmn_training', function () {
	if ( ! current_user_can( 'gcmn_view_tracker' ) || ! isset( $_POST['gcmn_training_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_training_nonce'] ) ), 'gcmn_training' ) ) {
		wp_die( 'Not allowed.', 403 );
	}
	$in     = isset( $_POST['t'] ) && is_array( $_POST['t'] ) ? wp_unslash( $_POST['t'] ) : array();
	$skills = gcmn_training_skills();
	$out    = array();
	foreach ( $in as $p ) {
		$name = isset( $p['name'] ) ? sanitize_text_field( $p['name'] ) : '';
		if ( '' === $name ) {
			continue;
		}
		$ticked = array();
		foreach ( $skills as $k => $label ) {
			if ( ! empty( $p['skills'][ $k ] ) ) {
				$ticked[ $k ] = 1;
			}
		}
		$out[] = array( 'name' => $name, 'email' => isset( $p['email'] ) ? sanitize_email( $p['email'] ) : '', 'skills' => $ticked );
	}
	update_option( 'gcmn_training', $out );
	wp_safe_redirect( add_query_arg( array( 'page' => 'gcmn-training', 'gcmn_msg' => rawurlencode( 'Training saved.' ) ), admin_url( 'admin.php' ) ) );
	exit;
} );

/* ---- 90-day plan ---- */
function gcmn_render_plan() {
	if ( ! current_user_can( 'gcmn_view_tracker' ) ) {
		wp_die( 'Not allowed.' );
	}
	$start = get_option( 'gcmn_plan_start', '' );
	$done  = get_option( 'gcmn_plan_done', array() );
	$done  = is_array( $done ) ? $done : array();
	$day   = $start ? max( 1, (int) floor( ( time() - strtotime( $start ) ) / DAY_IN_SECONDS ) + 1 ) : 0;
	echo '<div class="wrap"><h1>90-day plan</h1>';
	if ( isset( $_GET['gcmn_msg'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
		echo '<div class="notice notice-success is-dismissible"><p>' . esc_html( rawurldecode( sanitize_text_field( wp_unslash( $_GET['gcmn_msg'] ) ) ) ) . '</p></div>'; // phpcs:ignore WordPress.Security.NonceVerification
	}
	echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '">';
	wp_nonce_field( 'gcmn_plan', 'gcmn_plan_nonce' );
	echo '<input type="hidden" name="action" value="gcmn_plan"><p><label>Start date <input type="date" name="start" value="' . esc_attr( $start ) . '"></label>' . ( $day ? ' &nbsp; <strong>Day ' . (int) $day . ' of 90</strong>' : '' ) . '</p>';
	foreach ( gcmn_plan_phases() as $pi => $ph ) {
		echo '<h2>' . esc_html( $ph[0] ) . ': ' . esc_html( $ph[1] ) . '</h2><ul style="list-style:none;margin-left:0">';
		foreach ( $ph[2] as $ai => $a ) {
			$key = $pi . '-' . $ai;
			echo '<li><label><input type="checkbox" name="done[]" value="' . esc_attr( $key ) . '" ' . checked( in_array( $key, $done, true ), true, false ) . '> ' . esc_html( $a ) . '</label></li>';
		}
		echo '</ul>';
	}
	submit_button( 'Save the plan' );
	echo '</form></div>';
}

add_action( 'admin_post_gcmn_plan', function () {
	if ( ! current_user_can( 'gcmn_view_tracker' ) || ! isset( $_POST['gcmn_plan_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_plan_nonce'] ) ), 'gcmn_plan' ) ) {
		wp_die( 'Not allowed.', 403 );
	}
	$start = isset( $_POST['start'] ) && preg_match( '/^\d{4}-\d{2}-\d{2}$/', wp_unslash( $_POST['start'] ) ) ? wp_unslash( $_POST['start'] ) : '';
	$done  = isset( $_POST['done'] ) && is_array( $_POST['done'] ) ? array_values( array_filter( array_map( 'sanitize_text_field', wp_unslash( $_POST['done'] ) ), function ( $k ) {
		return (bool) preg_match( '/^\d-\d+$/', $k );
	} ) ) : array();
	update_option( 'gcmn_plan_start', $start );
	update_option( 'gcmn_plan_done', $done );
	wp_safe_redirect( add_query_arg( array( 'page' => 'gcmn-plan', 'gcmn_msg' => rawurlencode( 'Plan saved.' ) ), admin_url( 'admin.php' ) ) );
	exit;
} );
