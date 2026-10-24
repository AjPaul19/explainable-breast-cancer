<?php
defined( 'ABSPATH' ) || exit;

add_action( 'gcmn_daily', 'gcmn_run_daily' );

/** Safety net if the schedule was lost (for example after a restore). */
add_action( 'init', function () {
	if ( ! wp_next_scheduled( 'gcmn_daily' ) ) {
		wp_schedule_event( time() + HOUR_IN_SECONDS, 'daily', 'gcmn_daily' );
	}
} );

/**
 * Daily: take down anything whose date has passed, and remind owners about content past its review date.
 * Time-sensitive items (events, prayer needs, opportunities) never stay online after they expire.
 */
function gcmn_run_daily() {
	$today = gmdate( 'Y-m-d' );
	gcmn_expire_items( $today );
	$new = gcmn_queue_review_reminders( $today );
	gcmn_outbox_alert_admin( $new ); // tells the Website Administrator; nothing goes to any owner
	gcmn_monthly_review_reminder( $today );
}

function gcmn_expire_items( $today ) {
	$rules = array(
		'gcmn_event'       => '_gcmn_end',
		'gcmn_opportunity' => '_gcmn_expires',
		'gcmn_prayer'      => '_gcmn_expires',
	);
	foreach ( $rules as $type => $key ) {
		$ids = get_posts( array(
			'post_type'   => $type,
			'post_status' => 'publish',
			'numberposts' => 200,
			'fields'      => 'ids',
			'gcmn_all'    => true,
			'meta_query'  => array( array( 'key' => $key, 'value' => $today, 'compare' => '<', 'type' => 'DATE' ) ),
		) );
		foreach ( $ids as $id ) {
			wp_update_post( array( 'ID' => $id, 'post_status' => 'draft' ) );
		}
	}
	// Events without an end date leave after their start date.
	$ids = get_posts( array(
		'post_type' => 'gcmn_event', 'post_status' => 'publish', 'numberposts' => 200, 'fields' => 'ids', 'gcmn_all' => true,
		'meta_query' => array( 'relation' => 'AND', array( 'key' => '_gcmn_start', 'value' => $today, 'compare' => '<', 'type' => 'DATE' ), array( 'key' => '_gcmn_end', 'compare' => 'NOT EXISTS' ) ),
	) );
	foreach ( $ids as $id ) {
		wp_update_post( array( 'ID' => $id, 'post_status' => 'draft' ) );
	}
	// Prayer needs and others without an explicit end default to three weeks.
	$ids = get_posts( array(
		'post_type' => 'gcmn_prayer', 'post_status' => 'publish', 'numberposts' => 200, 'fields' => 'ids', 'gcmn_all' => true, 'date_query' => array( array( 'before' => '-21 days' ) ),
		'meta_query' => array( array( 'key' => '_gcmn_expires', 'compare' => 'NOT EXISTS' ) ),
	) );
	foreach ( $ids as $id ) {
		wp_update_post( array( 'ID' => $id, 'post_status' => 'draft' ) );
	}
}

/**
 * Find content past its review date and prepare a reminder for each owner. Nothing is sent to an owner here: the messages wait in
 * Website system > Owner emails until the Website Administrator sends them. Returns how many new messages were queued.
 */
function gcmn_queue_review_reminders( $today ) {
	$due = get_posts( array(
		'post_type'   => gcmn_workflow_types(),
		'post_status' => 'publish',
		'numberposts' => 300,
		'gcmn_all'    => true,
		'meta_query'  => array( array( 'key' => '_gcmn_review', 'value' => $today, 'compare' => '<=', 'type' => 'DATE' ) ),
	) );
	$new = 0;
	foreach ( $due as $p ) {
		if ( gcmn_is_functional_page( $p ) ) {
			continue;
		}
		update_post_meta( $p->ID, '_gcmn_needs_update', '1' );
		$dept   = get_post_meta( $p->ID, '_gcmn_dept', true );
		$review = get_post_meta( $p->ID, '_gcmn_review', true );
		$type   = get_post_type_object( $p->post_type )->labels->singular_name;
		$id     = gcmn_outbox_add( array(
			'to'      => $dept ? gcmn_dept_emails( $dept )['owner'] : '',
			'dept'    => $dept,
			'post_id' => $p->ID,
			'reason'  => 'stale',
			'key'     => 'stale:' . $p->ID . ':' . $review,
			'subject' => 'Please review: ' . $p->post_title,
			'body'    => "Hello,\n\nThe website item “{$p->post_title}” ({$type}) was due for review on " . gcmn_date( $review ) . ".\n\n"
				. "Please check that it is still correct. If it is, tell the Content Editor. If it is not, update it or tell the Content Editor to remove it.\n\n"
				. 'See it: ' . get_permalink( $p ) . "\n",
		) );
		if ( $id ) {
			$new++;
		}
	}
	return $new;
}

/** Once a month, remind Website Oversight and the Website Administrator that the monthly review is due. Internal people only. */
function gcmn_monthly_review_reminder( $today ) {
	$month = substr( $today, 0, 7 );
	if ( get_option( 'gcmn_monthly_sent' ) === $month ) {
		return false;
	}
	update_option( 'gcmn_monthly_sent', $month );
	$to = array_values( array_unique( array_filter( array( gcmn_email( 'oversight' ), gcmn_webadmin_email() ) ) ) );
	return wp_mail(
		$to,
		'Monthly website review is due',
		"It is time for the monthly website review.\n\nOpen it, answer the eight questions and finish with who, what and by when:\n" . admin_url( 'admin.php?page=gcmn-review' ) . "\n"
	);
}

/**
 * Visitors never see an expired event, opportunity or prayer need, even before the nightly job takes it offline.
 * Applied to every public query for those types.
 */
add_action( 'pre_get_posts', function ( $q ) {
	if ( is_admin() || $q->get( 'gcmn_all' ) || wp_doing_cron() ) {
		return; // the nightly job and admin screens must see expired items too
	}
	$type = $q->get( 'post_type' );
	$type = is_array( $type ) && 1 === count( $type ) ? $type[0] : $type;
	if ( $q->is_post_type_archive( 'gcmn_event' ) ) {
		$type = 'gcmn_event';
	} elseif ( $q->is_post_type_archive( 'gcmn_opportunity' ) ) {
		$type = 'gcmn_opportunity';
	} elseif ( $q->is_post_type_archive( 'gcmn_prayer' ) ) {
		$type = 'gcmn_prayer';
	}
	$today = gmdate( 'Y-m-d' );
	$mq    = (array) $q->get( 'meta_query' );
	if ( 'gcmn_event' === $type ) {
		$mq[] = array(
			'relation' => 'OR',
			array( 'key' => '_gcmn_end', 'value' => $today, 'compare' => '>=', 'type' => 'DATE' ),
			array( 'relation' => 'AND', array( 'key' => '_gcmn_end', 'compare' => 'NOT EXISTS' ), array( 'key' => '_gcmn_start', 'value' => $today, 'compare' => '>=', 'type' => 'DATE' ) ),
		);
	} elseif ( 'gcmn_opportunity' === $type || 'gcmn_prayer' === $type ) {
		$mq[] = array(
			'relation' => 'OR',
			array( 'key' => '_gcmn_expires', 'compare' => 'NOT EXISTS' ),
			array( 'key' => '_gcmn_expires', 'value' => $today, 'compare' => '>=', 'type' => 'DATE' ),
		);
	} else {
		return;
	}
	$q->set( 'meta_query', $mq );
}, 20 );

/** An expired item's own address returns "not found" too. */
add_action( 'template_redirect', function () {
	if ( ! is_singular( array( 'gcmn_event', 'gcmn_opportunity', 'gcmn_prayer' ) ) || current_user_can( 'edit_posts' ) ) {
		return;
	}
	$id    = get_queried_object_id();
	$today = gmdate( 'Y-m-d' );
	$type  = get_post_type( $id );
	$end   = 'gcmn_event' === $type ? ( get_post_meta( $id, '_gcmn_end', true ) ?: get_post_meta( $id, '_gcmn_start', true ) ) : get_post_meta( $id, '_gcmn_expires', true );
	if ( $end && $end < $today ) {
		global $wp_query;
		$wp_query->set_404();
		status_header( 404 );
		nocache_headers();
	}
} );
