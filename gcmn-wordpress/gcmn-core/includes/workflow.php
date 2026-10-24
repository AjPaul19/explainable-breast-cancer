<?php
defined( 'ABSPATH' ) || exit;

/**
 * The review workflow: submit, review, approve, publish, quality check, record.
 * The fields below are internal. They are never printed on the public site.
 */

/** Pages the plugin itself manages are not part of the review workflow. */
function gcmn_is_functional_page( $post ) {
	return $post && 'page' === $post->post_type && in_array( $post->post_name, array( 'home', 'news', 'contact', 'submit-content' ), true );
}

/** Staff write in the classic editor, so the review fields and the status change save in a single request. */
add_filter( 'use_block_editor_for_post_type', function ( $use, $type ) {
	return in_array( $type, gcmn_workflow_types(), true ) ? false : $use;
}, 10, 2 );

add_action( 'add_meta_boxes', function () {
	foreach ( gcmn_workflow_types() as $type ) {
		add_meta_box( 'gcmn_workflow', 'Review and approval', 'gcmn_render_workflow_box', $type, 'side', 'high' );
	}
} );

function gcmn_workflow_values( $post_id ) {
	$g = function ( $k ) use ( $post_id ) {
		return get_post_meta( $post_id, '_gcmn_' . $k, true );
	};
	return array(
		'dept'          => $g( 'dept' ),
		'approval'      => $g( 'approval' ) ?: 'none',
		'approved'      => $g( 'approved' ),
		'approver'      => $g( 'approver' ),
		'qc'            => $g( 'qc' ),
		'sensitive'     => $g( 'sensitive' ),
		'review'        => $g( 'review' ),
		'reviewed'      => $g( 'reviewed' ),
	);
}

function gcmn_render_workflow_box( $post ) {
	if ( gcmn_is_functional_page( $post ) ) {
		echo '<p>This page is managed by the plugin.</p>';
		return;
	}
	wp_nonce_field( 'gcmn_workflow', 'gcmn_workflow_nonce' );
	$v = gcmn_workflow_values( $post->ID );
	echo '<p><label for="gw-dept"><strong>Department or strategy</strong></label><br><select id="gw-dept" name="gcmn_w[dept]" style="width:100%"><option value="">Choose</option>';
	foreach ( array_keys( gcmn_departments() ) as $name ) {
		echo '<option ' . selected( $v['dept'], $name, false ) . '>' . esc_html( $name ) . '</option>';
	}
	echo '</select></p>';
	echo '<p><label for="gw-approval"><strong>Approval needed from</strong></label><br><select id="gw-approval" name="gcmn_w[approval]" style="width:100%">';
	foreach ( array( 'none' => 'None needed', 'strategy' => 'Strategy leader', 'leadership' => 'Leadership', 'finance' => 'Finance' ) as $k => $label ) {
		echo '<option value="' . esc_attr( $k ) . '" ' . selected( $v['approval'], $k, false ) . '>' . esc_html( $label ) . '</option>';
	}
	echo '</select></p>';
	echo '<p><label><input type="checkbox" name="gcmn_w[approved]" value="1" ' . checked( $v['approved'], '1', false ) . '> Approved</label><br><input type="text" name="gcmn_w[approver]" value="' . esc_attr( $v['approver'] ) . '" placeholder="Approved by (name)" style="width:100%"></p>';
	echo '<p><label><input type="checkbox" name="gcmn_w[sensitive]" value="1" ' . checked( $v['sensitive'], '1', false ) . '> Contains sensitive or restricted information (needs Leadership approval)</label></p>';
	echo '<p><label><input type="checkbox" name="gcmn_w[qc]" value="1" ' . checked( $v['qc'], '1', false ) . '> Quality check done: spelling, formatting, images, links, contact details and the mobile view.</label></p>';
	if ( current_user_can( 'gcmn_view_tracker' ) ) {
		echo '<p><label><input type="checkbox" name="gcmn_w[reviewed]" value="1" ' . checked( $v['reviewed'], '1', false ) . '> Reviewed by the Content Editor. If approval is needed, this emails the approver.</label></p>';
		echo '<p><label for="gw-changes"><strong>Ask the owner for changes</strong></label><br><textarea id="gw-changes" name="gcmn_w[changes]" rows="3" style="width:100%" placeholder="What needs to change?"></textarea><span class="description">This prepares an email to the content owner. It is <strong>not sent</strong> until the Website Administrator presses Send under Website system &gt; Owner emails.</span></p>';
	}
	$default = gmdate( 'Y-m-d', strtotime( '+' . gcmn_default_review_days( $post->post_type ) . ' days' ) );
	echo '<p><label for="gw-review"><strong>Next review</strong></label><br><input type="date" id="gw-review" name="gcmn_w[review]" value="' . esc_attr( $v['review'] ) . '" style="width:100%"><span class="description">Empty means ' . esc_html( gcmn_date( $default ) ) . '.</span></p>';
	$wanted = get_post_meta( $post->ID, '_gcmn_desired_date', true );
	if ( $wanted ) {
		echo '<p class="description">Requested publication date: <strong>' . esc_html( gcmn_date( $wanted ) ) . '</strong></p>';
	}
	echo '<p class="description">Stage: <strong>' . esc_html( gcmn_stage( $post ) ) . '</strong></p>';
}

add_action( 'save_post', function ( $post_id, $post ) {
	if ( ! isset( $_POST['gcmn_workflow_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_workflow_nonce'] ) ), 'gcmn_workflow' ) ) {
		return;
	}
	if ( ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) || ! current_user_can( 'edit_post', $post_id ) ) {
		return;
	}
	$in = isset( $_POST['gcmn_w'] ) && is_array( $_POST['gcmn_w'] ) ? wp_unslash( $_POST['gcmn_w'] ) : array();
	$approval = isset( $in['approval'] ) && in_array( $in['approval'], array( 'none', 'strategy', 'leadership', 'finance' ), true ) ? $in['approval'] : 'none';
	$review   = isset( $in['review'] ) && preg_match( '/^\d{4}-\d{2}-\d{2}$/', $in['review'] ) ? $in['review'] : '';
	$map = array(
		'dept'      => isset( $in['dept'] ) ? sanitize_text_field( $in['dept'] ) : '',
		'approval'  => $approval,
		'approved'  => ! empty( $in['approved'] ) ? '1' : '',
		'approver'  => isset( $in['approver'] ) ? sanitize_text_field( $in['approver'] ) : '',
		'sensitive' => ! empty( $in['sensitive'] ) ? '1' : '',
		'qc'        => ! empty( $in['qc'] ) ? '1' : '',
		'review'    => $review,
	);
	if ( current_user_can( 'gcmn_view_tracker' ) ) {
		$map['reviewed'] = ! empty( $in['reviewed'] ) ? '1' : '';
	}
	foreach ( $map as $k => $v ) {
		'' === $v ? delete_post_meta( $post_id, '_gcmn_' . $k ) : update_post_meta( $post_id, '_gcmn_' . $k, $v );
	}
	if ( current_user_can( 'gcmn_view_tracker' ) ) {
		gcmn_after_workflow_save( $post_id, $post, isset( $in['changes'] ) ? sanitize_textarea_field( $in['changes'] ) : '' );
	}
	if ( 'publish' === $post->post_status && ! get_post_meta( $post_id, '_gcmn_review', true ) ) {
		update_post_meta( $post_id, '_gcmn_review', gmdate( 'Y-m-d', strtotime( '+' . gcmn_default_review_days( $post->post_type ) . ' days' ) ) );
	}
	if ( 'publish' === $post->post_status ) {
		delete_post_meta( $post_id, '_gcmn_needs_update' );
	}
}, 20, 2 );

/** Who has to approve this item: leadership for anything sensitive, otherwise the approval chosen. 'none' when nobody. */
function gcmn_approval_needed( $post_id ) {
	$v = gcmn_workflow_values( $post_id );
	return $v['sensitive'] ? 'leadership' : $v['approval'];
}

/** The approver's email for an item, from the People settings. */
function gcmn_approver_email( $post_id ) {
	$need = gcmn_approval_needed( $post_id );
	if ( 'strategy' === $need ) {
		$dept = get_post_meta( $post_id, '_gcmn_dept', true );
		return ( $dept ? gcmn_dept_emails( $dept )['leader'] : '' ) ?: gcmn_email( 'leadership' ) ?: gcmn_webadmin_email();
	}
	if ( 'finance' === $need ) {
		return gcmn_email( 'finance' ) ?: gcmn_webadmin_email();
	}
	return gcmn_email( 'leadership' ) ?: gcmn_webadmin_email();
}

/**
 * After the Content Editor saves: (1) if the item is reviewed and needs approval, ask the approver once;
 * (2) if the editor wrote a change request, queue an email to the owner. That email is NOT sent: the Website Administrator sends it.
 */
function gcmn_after_workflow_save( $post_id, $post, $changes ) {
	$v    = gcmn_workflow_values( $post_id );
	$need = gcmn_approval_needed( $post_id );
	if ( $v['reviewed'] && 'none' !== $need && ! $v['approved'] && get_post_meta( $post_id, '_gcmn_approval_notified', true ) !== $need ) {
		$to = gcmn_approver_email( $post_id );
		wp_mail(
			$to,
			'Approval needed: ' . $post->post_title,
			"The Content Editor has reviewed a website item that needs your approval.\n\nItem: {$post->post_title}\nWho approves: " . ucfirst( $need ) . "\n\n"
			. 'Read it: ' . get_edit_post_link( $post_id, 'raw' ) . "\n\nTell the Content Editor your decision. They will record it and the item can then be published.\n"
		);
		update_post_meta( $post_id, '_gcmn_approval_notified', $need );
	}
	if ( '' !== $changes ) {
		$dept = $v['dept'];
		$id   = gcmn_outbox_add( array(
			'to'      => $dept ? gcmn_dept_emails( $dept )['owner'] : '',
			'dept'    => $dept,
			'post_id' => $post_id,
			'reason'  => 'changes',
			'key'     => 'changes:' . $post_id . ':' . md5( $changes ),
			'subject' => 'Changes needed: ' . $post->post_title,
			'body'    => "Hello,\n\nThe Content Editor has asked for changes to “{$post->post_title}”:\n\n{$changes}\n\nPlease update it and submit it again, or reply to the Website Administrator.\n\nOpen it: " . get_edit_post_link( $post_id, 'raw' ) . "\n",
		) );
		if ( $id ) {
			update_post_meta( $post_id, '_gcmn_changes_requested', gmdate( 'Y-m-d' ) );
			gcmn_outbox_alert_admin( 1 );
			set_transient( 'gcmn_notice_' . get_current_user_id(), 'An email to the content owner has been prepared. It is not sent until the Website Administrator presses Send under Website system > Owner emails.', 60 );
		}
	}
}

/**
 * Saving an item that is live counts as reviewing it: if its review date is empty or has passed, the next review moves out
 * by the default interval, and the "needs update" flag is cleared. This is how an owner confirms an item is still correct.
 */
add_action( 'save_post', function ( $post_id, $post ) {
	if ( wp_is_post_revision( $post_id ) || wp_is_post_autosave( $post_id ) || 'publish' !== $post->post_status || ! in_array( $post->post_type, gcmn_workflow_types(), true ) ) {
		return;
	}
	if ( gcmn_is_functional_page( $post ) || ( defined( 'GCMN_IMPORTING' ) && GCMN_IMPORTING ) ) {
		return;
	}
	$review = get_post_meta( $post_id, '_gcmn_review', true );
	if ( ! $review || $review < gmdate( 'Y-m-d' ) ) {
		update_post_meta( $post_id, '_gcmn_review', gmdate( 'Y-m-d', strtotime( '+' . gcmn_default_review_days( $post->post_type ) . ' days' ) ) );
	}
	delete_post_meta( $post_id, '_gcmn_needs_update' );
	delete_post_meta( $post_id, '_gcmn_changes_requested' );
}, 30, 2 );

/** Why this item may not be published yet. Returns a list of plain-language reasons, empty when it is ready. */
function gcmn_publish_blockers( $post_id, $post_type, $post_name, array $posted ) {
	$stored = gcmn_workflow_values( $post_id );
	$val = function ( $k ) use ( $posted, $stored ) {
		return array_key_exists( $k, $posted ) ? $posted[ $k ] : $stored[ $k ];
	};
	$why = array();
	if ( ! $val( 'qc' ) ) {
		$why[] = 'the quality check is not ticked';
	}
	$need = $val( 'approval' );
	if ( $val( 'sensitive' ) ) {
		$need = 'leadership';
	}
	if ( $need && 'none' !== $need && ! $val( 'approved' ) ) {
		$why[] = 'it needs approval first';
	}
	if ( 'gcmn_story' === $post_type ) {
		$consent = isset( $_POST['gcmn_d']['consent'] ) ? ! empty( $_POST['gcmn_d']['consent'] ) : (bool) get_post_meta( $post_id, '_gcmn_consent', true ); // phpcs:ignore WordPress.Security.NonceVerification
		if ( ! $consent ) {
			$why[] = 'the people in the story have not confirmed their consent';
		}
	}
	return $why;
}

/** Block publishing until the gates are met. The item drops back to "pending review" instead and the editor is told why. */
add_filter( 'wp_insert_post_data', function ( $data, $postarr ) {
	if ( ! in_array( $data['post_type'], gcmn_workflow_types(), true ) || ! in_array( $data['post_status'], array( 'publish', 'future' ), true ) ) {
		return $data;
	}
	if ( defined( 'GCMN_IMPORTING' ) && GCMN_IMPORTING ) {
		return $data;
	}
	$post_id = isset( $postarr['ID'] ) ? (int) $postarr['ID'] : 0;
	if ( ( $post_id && gcmn_is_functional_page( get_post( $post_id ) ) ) || in_array( $data['post_name'], array( 'home', 'news', 'contact', 'submit-content' ), true ) ) {
		return $data;
	}
	$posted = array();
	if ( isset( $_POST['gcmn_workflow_nonce'] ) && wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_workflow_nonce'] ) ), 'gcmn_workflow' ) ) {
		$w = isset( $_POST['gcmn_w'] ) && is_array( $_POST['gcmn_w'] ) ? wp_unslash( $_POST['gcmn_w'] ) : array();
		$posted = array(
			'qc'        => ! empty( $w['qc'] ) ? '1' : '',
			'approved'  => ! empty( $w['approved'] ) ? '1' : '',
			'sensitive' => ! empty( $w['sensitive'] ) ? '1' : '',
			'approval'  => isset( $w['approval'] ) ? sanitize_key( $w['approval'] ) : 'none',
		);
	}
	$why = gcmn_publish_blockers( $post_id, $data['post_type'], $data['post_name'], $posted );
	if ( $why ) {
		$data['post_status'] = 'pending';
		set_transient( 'gcmn_notice_' . get_current_user_id(), 'Not published yet: ' . implode( '; ', $why ) . '. It is saved as pending review.', 60 );
	}
	return $data;
}, 20, 2 );

add_action( 'admin_notices', function () {
	$n = get_transient( 'gcmn_notice_' . get_current_user_id() );
	if ( $n ) {
		delete_transient( 'gcmn_notice_' . get_current_user_id() );
		echo '<div class="notice notice-warning is-dismissible"><p>' . esc_html( $n ) . '</p></div>';
	}
} );

/** Where an item is in the workflow, in plain words. */
function gcmn_stage( $post ) {
	$post = get_post( $post );
	if ( ! $post ) {
		return '';
	}
	$v = gcmn_workflow_values( $post->ID );
	if ( 'publish' === $post->post_status ) {
		return ( $v['review'] && $v['review'] < gmdate( 'Y-m-d' ) ) ? 'Needs update' : 'Published';
	}
	if ( 'pending' === $post->post_status ) {
		$need = $v['sensitive'] ? 'leadership' : $v['approval'];
		if ( ! $v['reviewed'] && ! $v['approved'] ) {
			return get_post_meta( $post->ID, '_gcmn_changes_requested', true ) ? 'Changes requested' : 'In review';
		}
		if ( 'none' !== $need && ! $v['approved'] ) {
			return 'Awaiting approval';
		}
		return $v['qc'] ? 'Ready to publish' : 'Approved';
	}
	return 'private' === $post->post_status ? 'Private' : 'Draft';
}

/* ---- columns and filters on the standard lists ---- */
add_action( 'admin_init', function () {
	foreach ( gcmn_workflow_types() as $type ) {
		add_filter( "manage_{$type}_posts_columns", function ( $c ) {
			$c['gcmn_stage'] = 'Stage';
			$c['gcmn_dept']  = 'Department';
			$c['gcmn_review'] = 'Next review';
			return $c;
		} );
		add_action( "manage_{$type}_posts_custom_column", function ( $col, $id ) {
			if ( 'gcmn_stage' === $col ) {
				echo esc_html( gcmn_stage( $id ) );
			} elseif ( 'gcmn_dept' === $col ) {
				echo esc_html( get_post_meta( $id, '_gcmn_dept', true ) );
			} elseif ( 'gcmn_review' === $col ) {
				echo esc_html( gcmn_date( get_post_meta( $id, '_gcmn_review', true ) ) );
			}
		}, 10, 2 );
		add_filter( "manage_edit-{$type}_sortable_columns", function ( $c ) {
			$c['gcmn_review'] = 'gcmn_review';
			return $c;
		} );
	}
} );

add_action( 'pre_get_posts', function ( $q ) {
	if ( is_admin() && $q->is_main_query() && 'gcmn_review' === $q->get( 'orderby' ) ) {
		$q->set( 'meta_key', '_gcmn_review' );
		$q->set( 'orderby', 'meta_value' );
	}
} );

/* ---- the content tracker: every item, its stage, approver and next review ---- */

function gcmn_tracker_rows( $filters ) {
	$rows  = array();
	$posts = get_posts( array(
		'post_type'   => gcmn_workflow_types(),
		'post_status' => array( 'publish', 'pending', 'draft', 'private' ),
		'numberposts' => 500,
		'orderby'     => 'modified',
		'order'       => 'DESC',
	) );
	foreach ( $posts as $p ) {
		if ( gcmn_is_functional_page( $p ) ) {
			continue;
		}
		$v  = gcmn_workflow_values( $p->ID );
		$row = array(
			'id'       => $p->ID,
			'title'    => $p->post_title ?: '(no title)',
			'type'     => get_post_type_object( $p->post_type )->labels->singular_name,
			'dept'     => $v['dept'],
			'stage'    => gcmn_stage( $p ),
			'approver' => $v['approver'],
			'date'     => 'publish' === $p->post_status ? gcmn_date( $p->post_date ) : '',
			'review'   => $v['review'] ? gcmn_date( $v['review'] ) : '',
		);
		if ( $filters['stage'] && $row['stage'] !== $filters['stage'] ) {
			continue;
		}
		if ( $filters['dept'] && $row['dept'] !== $filters['dept'] ) {
			continue;
		}
		$rows[] = $row;
	}
	return $rows;
}

function gcmn_render_tracker() {
	if ( ! current_user_can( 'gcmn_view_tracker' ) ) {
		return;
	}
	$stages  = array( 'Draft', 'In review', 'Changes requested', 'Awaiting approval', 'Approved', 'Ready to publish', 'Published', 'Needs update' );
	$filters = array(
		'stage' => isset( $_GET['stage'] ) && in_array( wp_unslash( $_GET['stage'] ), $stages, true ) ? wp_unslash( $_GET['stage'] ) : '', // phpcs:ignore WordPress.Security.NonceVerification
		'dept'  => isset( $_GET['dept'] ) ? sanitize_text_field( wp_unslash( $_GET['dept'] ) ) : '', // phpcs:ignore WordPress.Security.NonceVerification
	);
	if ( isset( $_GET['gcmn_csv'] ) && check_admin_referer( 'gcmn_csv' ) ) {
		header( 'Content-Type: text/csv; charset=utf-8' );
		header( 'Content-Disposition: attachment; filename="gcmn-content-tracker-' . gmdate( 'Y-m-d' ) . '.csv"' );
		$out = fopen( 'php://output', 'w' );
		fputcsv( $out, array( 'Title', 'Type', 'Department', 'Stage', 'Approved by', 'Published', 'Next review' ) );
		foreach ( gcmn_tracker_rows( $filters ) as $r ) {
			// Guard against spreadsheet formulas in cells.
			$cells = array( $r['title'], $r['type'], $r['dept'], $r['stage'], $r['approver'], $r['date'], $r['review'] );
			fputcsv( $out, array_map( function ( $c ) {
				return preg_match( '/^[=+\-@]/', (string) $c ) ? "'" . $c : $c;
			}, $cells ) );
		}
		exit;
	}
	echo '<div class="wrap"><h1>Content tracker</h1><form method="get"><input type="hidden" name="page" value="gcmn-tracker"><p>';
	echo '<select name="stage"><option value="">Every stage</option>';
	foreach ( $stages as $s ) {
		echo '<option ' . selected( $filters['stage'], $s, false ) . '>' . esc_html( $s ) . '</option>';
	}
	echo '</select> <select name="dept"><option value="">Every department</option>';
	foreach ( array_keys( gcmn_departments() ) as $d ) {
		echo '<option ' . selected( $filters['dept'], $d, false ) . '>' . esc_html( $d ) . '</option>';
	}
	echo '</select> <button class="button">Filter</button> <a class="button" href="' . esc_url( wp_nonce_url( add_query_arg( array_merge( $filters, array( 'page' => 'gcmn-tracker', 'gcmn_csv' => 1 ) ), admin_url( 'admin.php' ) ), 'gcmn_csv' ) ) . '">Download CSV</a></p></form>';
	echo '<table class="widefat striped"><thead><tr><th>Title</th><th>Type</th><th>Department</th><th>Stage</th><th>Approved by</th><th>Published</th><th>Next review</th></tr></thead><tbody>';
	$rows = gcmn_tracker_rows( $filters );
	if ( ! $rows ) {
		echo '<tr><td colspan="7">Nothing matches.</td></tr>';
	}
	foreach ( $rows as $r ) {
		echo '<tr><td><a href="' . esc_url( get_edit_post_link( $r['id'] ) ) . '">' . esc_html( $r['title'] ) . '</a></td><td>' . esc_html( $r['type'] ) . '</td><td>' . esc_html( $r['dept'] ) . '</td><td>' . esc_html( $r['stage'] ) . '</td><td>' . esc_html( $r['approver'] ) . '</td><td>' . esc_html( $r['date'] ) . '</td><td>' . esc_html( $r['review'] ) . '</td></tr>';
	}
	echo '</tbody></table></div>';
}
