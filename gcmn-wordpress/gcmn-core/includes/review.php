<?php
defined( 'ABSPATH' ) || exit;

/**
 * Monthly website review (Website Implementation System, section 10).
 * The eight questions are answered from the site's own data wherever possible. Every review ends with WHO -> WHAT -> BY WHEN.
 */
function gcmn_reviews() {
	$r = get_option( 'gcmn_reviews', array() );
	return is_array( $r ) ? $r : array();
}

function gcmn_review_draft() {
	$d = get_option( 'gcmn_review_draft', array() );
	return is_array( $d ) ? $d : array();
}

/** Facts for the review month, read from the site. */
function gcmn_review_facts( $month ) {
	$start = $month . '-01';
	$end   = gmdate( 'Y-m-d', strtotime( $start . ' +1 month' ) );
	$types = gcmn_workflow_types();
	$q = function ( array $extra ) use ( $types ) {
		return get_posts( array_merge( array( 'post_type' => $types, 'numberposts' => 100, 'gcmn_all' => true, 'orderby' => 'date', 'order' => 'DESC' ), $extra ) );
	};
	$published = $q( array( 'post_status' => 'publish', 'date_query' => array( array( 'after' => $start, 'before' => $end, 'inclusive' => true ) ) ) );
	$waiting   = $q( array( 'post_status' => 'pending' ) );
	$outdated  = $q( array( 'post_status' => 'publish', 'meta_query' => array( array( 'key' => '_gcmn_review', 'value' => gmdate( 'Y-m-d' ), 'compare' => '<', 'type' => 'DATE' ) ) ) );
	$events    = get_posts( array( 'post_type' => 'gcmn_event', 'post_status' => 'publish', 'numberposts' => 20, 'meta_key' => '_gcmn_start', 'orderby' => 'meta_value', 'order' => 'ASC',
		'meta_query' => array( array( 'key' => '_gcmn_start', 'value' => array( gmdate( 'Y-m-d' ), gmdate( 'Y-m-d', strtotime( '+45 days' ) ) ), 'compare' => 'BETWEEN', 'type' => 'DATE' ) ) ) );
	$clear = array(
		'Giving: at least one approved account is published' => (bool) gcmn_giving_accounts(),
		'Partnership: the Partner page exists' => (bool) get_page_by_path( 'partnership' ),
		'Serve: the Serve page exists' => (bool) get_page_by_path( 'serve' ),
		'Contact: a public email or phone is set' => (bool) ( gcmn_opt( 'email' ) || gcmn_opt( 'phone' ) ),
	);
	return compact( 'published', 'waiting', 'outdated', 'events', 'clear' );
}

function gcmn_review_list( $posts, $empty ) {
	if ( ! $posts ) {
		return '<p><em>' . esc_html( $empty ) . '</em></p>';
	}
	$out = '<ul style="margin-left:1.2em;list-style:disc">';
	foreach ( array_slice( $posts, 0, 12 ) as $p ) {
		$out .= '<li><a href="' . esc_url( get_edit_post_link( $p->ID ) ) . '">' . esc_html( $p->post_title ?: '(no title)' ) . '</a> <span class="description">(' . esc_html( gcmn_stage( $p ) ) . ')</span></li>';
	}
	if ( count( $posts ) > 12 ) {
		$out .= '<li><em>and ' . ( count( $posts ) - 12 ) . ' more (see the Content tracker)</em></li>';
	}
	return $out . '</ul>';
}

function gcmn_render_review() {
	if ( ! current_user_can( 'gcmn_view_tracker' ) ) {
		wp_die( 'Not allowed.' );
	}
	$month   = gmdate( 'Y-m' );
	$facts   = gcmn_review_facts( $month );
	$draft   = gcmn_review_draft();
	$done    = gcmn_reviews();
	$actions = isset( $draft['actions'] ) && is_array( $draft['actions'] ) ? $draft['actions'] : array();
	while ( count( $actions ) < 4 ) {
		$actions[] = array( 'who' => '', 'email' => '', 'what' => '', 'by' => '' );
	}
	echo '<div class="wrap"><h1>Monthly website review: ' . esc_html( wp_date( 'F Y', strtotime( $month . '-01' ) ) ) . '</h1>';
	if ( isset( $done[ $month ] ) ) {
		echo '<div class="notice notice-success"><p>This month’s review was completed on ' . esc_html( gcmn_date( $done[ $month ]['date'] ) ) . '.</p></div>';
	}
	if ( isset( $_GET['gcmn_msg'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
		echo '<div class="notice notice-info is-dismissible"><p>' . esc_html( rawurldecode( sanitize_text_field( wp_unslash( $_GET['gcmn_msg'] ) ) ) ) . '</p></div>'; // phpcs:ignore WordPress.Security.NonceVerification
	}
	echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '">';
	wp_nonce_field( 'gcmn_review', 'gcmn_review_nonce' );
	echo '<input type="hidden" name="action" value="gcmn_review"><input type="hidden" name="month" value="' . esc_attr( $month ) . '">';
	echo '<h2>1. What was published this month?</h2>' . gcmn_review_list( $facts['published'], 'Nothing yet this month.' );
	echo '<h2>2. What content is waiting for review or publication?</h2>' . gcmn_review_list( $facts['waiting'], 'Nothing is waiting.' );
	echo '<h2>3. Which pages are outdated?</h2>' . gcmn_review_list( $facts['outdated'], 'No page is past its review date.' );
	echo '<h2>4. What ministry activities are coming up?</h2>' . gcmn_review_list( $facts['events'], 'No events in the next 45 days.' );
	$stories = get_posts( array( 'post_type' => 'gcmn_story', 'post_status' => 'publish', 'numberposts' => 50, 'orderby' => 'title', 'order' => 'ASC', 'gcmn_all' => true ) );
	$picked  = isset( $draft['featured'] ) && is_array( $draft['featured'] ) ? array_map( 'intval', $draft['featured'] ) : array();
	echo '<h2>5. Which stories should be featured?</h2><p><select name="featured[]" multiple size="6" style="min-width:340px">';
	foreach ( $stories as $s ) {
		echo '<option value="' . (int) $s->ID . '" ' . selected( in_array( $s->ID, $picked, true ), true, false ) . '>' . esc_html( $s->post_title ) . '</option>';
	}
	echo '</select></p><p class="description">Hold Ctrl or Cmd to choose more than one. The home page shows the newest stories, so feature a story by editing its date to today.</p>';
	echo '<h2>6. Are partnership, giving and service opportunities clear?</h2><ul style="margin-left:1.2em;list-style:disc">';
	foreach ( $facts['clear'] as $label => $ok ) {
		echo '<li>' . ( $ok ? '✓ ' : '✗ ' ) . esc_html( $label ) . '</li>';
	}
	echo '</ul>';
	echo '<h2>7. Are there broken links or incorrect contact details?</h2><p><label><input type="checkbox" name="checked" value="1" ' . checked( ! empty( $draft['checked'] ), true, false ) . '> I checked the links and tested every phone number and email on the Contact page this month.</label></p>';
	echo '<h2>8. What should be updated next month?</h2><p><textarea name="next" rows="3" class="large-text">' . esc_textarea( isset( $draft['next'] ) ? $draft['next'] : '' ) . '</textarea></p>';
	echo '<h2>Who → What → By when</h2><p class="description">Every review ends with clear actions. Add the person’s email to prepare a message for the Website Administrator to send.</p>';
	echo '<table class="widefat striped" style="max-width:1000px"><thead><tr><th>Who</th><th>Email (optional)</th><th>What</th><th>By when</th><th>Done</th></tr></thead><tbody>';
	foreach ( $actions as $i => $a ) {
		echo '<tr><td><input type="text" name="act[' . (int) $i . '][who]" value="' . esc_attr( $a['who'] ) . '"></td><td><input type="email" name="act[' . (int) $i . '][email]" value="' . esc_attr( $a['email'] ) . '"></td><td><input type="text" class="regular-text" name="act[' . (int) $i . '][what]" value="' . esc_attr( $a['what'] ) . '"></td><td><input type="date" name="act[' . (int) $i . '][by]" value="' . esc_attr( $a['by'] ) . '"></td><td><input type="checkbox" name="act[' . (int) $i . '][done]" value="1" ' . checked( ! empty( $a['done'] ), true, false ) . '></td></tr>';
	}
	echo '</tbody></table><p><button class="button" name="op" value="save">Save</button> <button class="button button-primary" name="op" value="complete">Complete this month’s review</button></p></form>';
	if ( $done ) {
		krsort( $done );
		echo '<h2>Reviews completed</h2><table class="widefat striped" style="max-width:700px"><thead><tr><th>Month</th><th>Completed</th><th>Actions</th></tr></thead><tbody>';
		foreach ( array_slice( $done, 0, 12, true ) as $m => $r ) {
			echo '<tr><td>' . esc_html( wp_date( 'F Y', strtotime( $m . '-01' ) ) ) . '</td><td>' . esc_html( gcmn_date( $r['date'] ) ) . '</td><td>' . (int) count( $r['actions'] ) . '</td></tr>';
		}
		echo '</tbody></table>';
	}
	echo '</div>';
}

add_action( 'admin_post_gcmn_review', function () {
	if ( ! current_user_can( 'gcmn_view_tracker' ) || ! isset( $_POST['gcmn_review_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_review_nonce'] ) ), 'gcmn_review' ) ) {
		wp_die( 'Not allowed.', 403 );
	}
	$month   = isset( $_POST['month'] ) && preg_match( '/^\d{4}-\d{2}$/', wp_unslash( $_POST['month'] ) ) ? wp_unslash( $_POST['month'] ) : gmdate( 'Y-m' );
	$raw     = isset( $_POST['act'] ) && is_array( $_POST['act'] ) ? wp_unslash( $_POST['act'] ) : array();
	$actions = array();
	$queued  = 0;
	foreach ( $raw as $a ) {
		$what = isset( $a['what'] ) ? sanitize_text_field( $a['what'] ) : '';
		$who  = isset( $a['who'] ) ? sanitize_text_field( $a['who'] ) : '';
		if ( '' === $what && '' === $who ) {
			continue;
		}
		$by    = isset( $a['by'] ) && preg_match( '/^\d{4}-\d{2}-\d{2}$/', $a['by'] ) ? $a['by'] : '';
		$email = isset( $a['email'] ) ? sanitize_email( $a['email'] ) : '';
		$actions[] = array( 'who' => $who, 'email' => $email, 'what' => $what, 'by' => $by, 'done' => ! empty( $a['done'] ) );
		if ( is_email( $email ) && $what && empty( $a['done'] ) ) {
			$id = gcmn_outbox_add( array(
				'to'      => $email,
				'reason'  => 'action',
				'key'     => 'action:' . $month . ':' . md5( $email . $what . $by ),
				'subject' => 'Website action for you: ' . $what,
				'body'    => "Hello {$who},\n\nFrom this month’s website review, the action for you is:\n\n{$what}\n" . ( $by ? 'By: ' . gcmn_date( $by ) . "\n" : '' ) . "\nPlease reply to the Website Administrator when it is done.\n",
			) );
			if ( $id ) {
				$queued++;
			}
		}
	}
	$draft = array(
		'month'    => $month,
		'featured' => isset( $_POST['featured'] ) && is_array( $_POST['featured'] ) ? array_map( 'absint', wp_unslash( $_POST['featured'] ) ) : array(),
		'checked'  => ! empty( $_POST['checked'] ),
		'next'     => isset( $_POST['next'] ) ? sanitize_textarea_field( wp_unslash( $_POST['next'] ) ) : '',
		'actions'  => $actions,
	);
	update_option( 'gcmn_review_draft', $draft );
	$msg = 'Saved.';
	if ( isset( $_POST['op'] ) && 'complete' === $_POST['op'] ) {
		$facts   = gcmn_review_facts( $month );
		$reviews = gcmn_reviews();
		$reviews[ $month ] = array(
			'date'    => gmdate( 'Y-m-d' ),
			'by'      => get_current_user_id(),
			'actions' => $actions,
			'next'    => $draft['next'],
			'summary' => array( 'published' => count( $facts['published'] ), 'waiting' => count( $facts['waiting'] ), 'outdated' => count( $facts['outdated'] ) ),
		);
		update_option( 'gcmn_reviews', $reviews );
		update_option( 'gcmn_review_draft', array() );
		$msg = 'The review for ' . wp_date( 'F Y', strtotime( $month . '-01' ) ) . ' is complete.';
	}
	if ( $queued ) {
		gcmn_outbox_alert_admin( $queued );
		$msg .= " {$queued} email" . ( 1 === $queued ? '' : 's' ) . ' prepared for the Website Administrator to send.';
	}
	wp_safe_redirect( add_query_arg( array( 'page' => 'gcmn-review', 'gcmn_msg' => rawurlencode( $msg ) ), admin_url( 'admin.php' ) ) );
	exit;
} );
