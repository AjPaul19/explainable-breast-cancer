<?php
defined( 'ABSPATH' ) || exit;

/**
 * Owner emails: messages to content owners (review reminders, changes requested, audit follow-ups).
 * NOTHING in this plugin emails a content owner by itself. Every such message is queued here, the Website Administrator is told
 * that messages are waiting, and a message leaves only when that person presses Send.
 */
add_action( 'init', function () {
	register_post_type( 'gcmn_outbox', array(
		'labels'          => array( 'name' => 'Owner emails', 'singular_name' => 'Owner email' ),
		'public'          => false,
		'show_ui'         => false,
		'supports'        => array( 'title', 'editor' ),
		'capability_type' => 'post',
	) );
} );

/**
 * Queue a message for the Website Administrator to decide on.
 * $a: to (may be empty), dept, subject, body, post_id, reason (stale|changes|audit|action), key (dedupe: one queued or sent message per key).
 * Returns the outbox ID, or 0 if an identical message was already queued or sent.
 */
function gcmn_outbox_add( array $a ) {
	$key = isset( $a['key'] ) ? (string) $a['key'] : '';
	if ( $key ) {
		$dupe = get_posts( array( 'post_type' => 'gcmn_outbox', 'post_status' => 'any', 'numberposts' => 1, 'fields' => 'ids', 'gcmn_all' => true,
			'meta_query' => array( array( 'key' => '_gcmn_key', 'value' => $key ) ) ) );
		if ( $dupe ) {
			return 0;
		}
	}
	$id = wp_insert_post( array(
		'post_type'    => 'gcmn_outbox',
		'post_status'  => 'private',
		'post_title'   => sanitize_text_field( $a['subject'] ),
		'post_content' => sanitize_textarea_field( $a['body'] ),
	) );
	if ( ! $id || is_wp_error( $id ) ) {
		return 0;
	}
	update_post_meta( $id, '_gcmn_state', 'queued' );
	update_post_meta( $id, '_gcmn_to', isset( $a['to'] ) && is_email( $a['to'] ) ? $a['to'] : '' );
	update_post_meta( $id, '_gcmn_dept', isset( $a['dept'] ) ? sanitize_text_field( $a['dept'] ) : '' );
	update_post_meta( $id, '_gcmn_item', isset( $a['post_id'] ) ? (int) $a['post_id'] : 0 );
	update_post_meta( $id, '_gcmn_reason', isset( $a['reason'] ) ? sanitize_key( $a['reason'] ) : '' );
	if ( $key ) {
		update_post_meta( $id, '_gcmn_key', $key );
	}
	return (int) $id;
}

function gcmn_outbox_items( $state = 'queued', $limit = 200 ) {
	return get_posts( array(
		'post_type' => 'gcmn_outbox', 'post_status' => 'private', 'numberposts' => $limit, 'orderby' => 'date', 'order' => 'DESC', 'gcmn_all' => true,
		'meta_query' => array( array( 'key' => '_gcmn_state', 'value' => $state ) ),
	) );
}

function gcmn_outbox_count() {
	return count( gcmn_outbox_items( 'queued', 500 ) );
}

/** Send one queued message. Only called from the administrator's Send button. Returns true, or a plain-language reason it was not sent. */
function gcmn_outbox_send( $id, $to = '', $subject = '', $body = '' ) {
	$post = get_post( $id );
	if ( ! $post || 'gcmn_outbox' !== $post->post_type || 'queued' !== get_post_meta( $id, '_gcmn_state', true ) ) {
		return 'That message is not waiting any more.';
	}
	$to = $to ?: get_post_meta( $id, '_gcmn_to', true );
	if ( ! is_email( $to ) ) {
		return 'There is no valid email address for “' . $post->post_title . '”. Type one in and press Send again.';
	}
	$subject = $subject ?: $post->post_title;
	$body    = $body ?: $post->post_content;
	$headers = array( 'Reply-To: ' . gcmn_webadmin_email() );
	$ok      = wp_mail( $to, $subject, $body . "\n\n--\nSent by the Website Administrator, " . get_bloginfo( 'name' ) . "\n", $headers );
	if ( ! $ok ) {
		return 'The email could not be sent. Check the site’s email settings.';
	}
	update_post_meta( $id, '_gcmn_state', 'sent' );
	update_post_meta( $id, '_gcmn_to', $to );
	update_post_meta( $id, '_gcmn_sent_by', get_current_user_id() );
	update_post_meta( $id, '_gcmn_sent_at', gmdate( 'Y-m-d H:i:s' ) );
	wp_update_post( array( 'ID' => $id, 'post_title' => $subject, 'post_content' => $body ) );
	return true;
}

/** One alert to the Website Administrator that messages are waiting. Returns true if sent. */
function gcmn_outbox_alert_admin( $new ) {
	if ( $new < 1 ) {
		return false;
	}
	$n = gcmn_outbox_count();
	return wp_mail(
		gcmn_webadmin_email(),
		sprintf( '%d email%s waiting for your decision (%s)', $n, 1 === $n ? '' : 's', get_bloginfo( 'name' ) ),
		"Some website content needs attention. Messages to the content owners have been prepared, but none has been sent.\n\n"
		. "You decide: open the list, read each message, then send it, change it or dismiss it.\n"
		. admin_url( 'admin.php?page=gcmn-owner-emails' ) . "\n"
	);
}

/* ---- the Owner emails screen ---- */
function gcmn_render_outbox() {
	if ( ! current_user_can( 'gcmn_send_owner_emails' ) ) {
		wp_die( 'Only the Website Administrator can send these emails.' );
	}
	$queued = gcmn_outbox_items( 'queued' );
	$reasons = array( 'stale' => 'Past its review date', 'changes' => 'Changes requested', 'audit' => 'Audit follow-up', 'action' => 'Monthly review action' );
	echo '<div class="wrap"><h1>Owner emails</h1><p>Nothing here has been sent. Each message goes only when you press <strong>Send</strong>. You can change the address and the words first, or dismiss a message you do not want to send.</p>';
	if ( isset( $_GET['gcmn_msg'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
		echo '<div class="notice notice-info is-dismissible"><p>' . esc_html( rawurldecode( sanitize_text_field( wp_unslash( $_GET['gcmn_msg'] ) ) ) ) . '</p></div>'; // phpcs:ignore WordPress.Security.NonceVerification
	}
	if ( ! $queued ) {
		echo '<p><strong>Nothing is waiting.</strong></p>';
	}
	if ( count( $queued ) > 1 ) {
		echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '" style="margin:12px 0">';
		wp_nonce_field( 'gcmn_outbox', 'gcmn_outbox_nonce' );
		echo '<input type="hidden" name="action" value="gcmn_outbox"><input type="hidden" name="op" value="send_all"><button class="button button-primary" onclick="return confirm(\'Send every message that has an email address?\')">Send all that have an address (' . (int) count( $queued ) . ')</button></form>';
	}
	foreach ( $queued as $m ) {
		$to   = get_post_meta( $m->ID, '_gcmn_to', true );
		$item = (int) get_post_meta( $m->ID, '_gcmn_item', true );
		$why  = isset( $reasons[ get_post_meta( $m->ID, '_gcmn_reason', true ) ] ) ? $reasons[ get_post_meta( $m->ID, '_gcmn_reason', true ) ] : 'Message';
		echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '" style="background:#fff;border:1px solid #c3c4c7;padding:12px 16px;margin:12px 0;max-width:900px">';
		wp_nonce_field( 'gcmn_outbox', 'gcmn_outbox_nonce' );
		echo '<input type="hidden" name="action" value="gcmn_outbox"><input type="hidden" name="id" value="' . (int) $m->ID . '">';
		echo '<p><strong>' . esc_html( $why ) . '</strong>' . ( get_post_meta( $m->ID, '_gcmn_dept', true ) ? ' · ' . esc_html( get_post_meta( $m->ID, '_gcmn_dept', true ) ) : '' );
		if ( $item && get_post( $item ) ) {
			echo ' · <a href="' . esc_url( get_edit_post_link( $item ) ) . '">' . esc_html( get_the_title( $item ) ) . '</a>';
		}
		echo '</p><p><label>To <input type="email" name="to" value="' . esc_attr( $to ) . '" class="regular-text" placeholder="owner@example.org"></label>' . ( $to ? '' : ' <em>No email on file. Add one here, or under Settings.</em>' ) . '</p>';
		echo '<p><label>Subject<br><input type="text" name="subject" value="' . esc_attr( $m->post_title ) . '" class="large-text"></label></p>';
		echo '<p><label>Message<br><textarea name="body" rows="6" class="large-text">' . esc_textarea( $m->post_content ) . '</textarea></label></p>';
		echo '<p><button class="button button-primary" name="op" value="send">Send</button> <button class="button" name="op" value="dismiss">Dismiss</button></p></form>';
	}
	$sent = gcmn_outbox_items( 'sent', 30 );
	if ( $sent ) {
		echo '<h2>Recently sent</h2><table class="widefat striped" style="max-width:900px"><thead><tr><th>Sent</th><th>To</th><th>Subject</th></tr></thead><tbody>';
		foreach ( $sent as $m ) {
			echo '<tr><td>' . esc_html( get_post_meta( $m->ID, '_gcmn_sent_at', true ) ) . '</td><td>' . esc_html( get_post_meta( $m->ID, '_gcmn_to', true ) ) . '</td><td>' . esc_html( $m->post_title ) . '</td></tr>';
		}
		echo '</tbody></table>';
	}
	echo '</div>';
}

add_action( 'admin_post_gcmn_outbox', function () {
	if ( ! current_user_can( 'gcmn_send_owner_emails' ) || ! isset( $_POST['gcmn_outbox_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_outbox_nonce'] ) ), 'gcmn_outbox' ) ) {
		wp_die( 'Not allowed.', 403 );
	}
	$op  = isset( $_POST['op'] ) ? sanitize_key( wp_unslash( $_POST['op'] ) ) : '';
	$msg = '';
	if ( 'send_all' === $op ) {
		$sent = 0;
		$skipped = 0;
		foreach ( gcmn_outbox_items( 'queued', 500 ) as $m ) {
			true === gcmn_outbox_send( $m->ID ) ? $sent++ : $skipped++;
		}
		$msg = sprintf( 'Sent %d. %d had no address and are still waiting.', $sent, $skipped );
	} else {
		$id = isset( $_POST['id'] ) ? absint( $_POST['id'] ) : 0;
		if ( 'send' === $op ) {
			$r   = gcmn_outbox_send(
				$id,
				isset( $_POST['to'] ) ? sanitize_email( wp_unslash( $_POST['to'] ) ) : '',
				isset( $_POST['subject'] ) ? sanitize_text_field( wp_unslash( $_POST['subject'] ) ) : '',
				isset( $_POST['body'] ) ? sanitize_textarea_field( wp_unslash( $_POST['body'] ) ) : ''
			);
			$msg = true === $r ? 'Sent.' : $r;
		} elseif ( 'dismiss' === $op && $id && 'gcmn_outbox' === get_post_type( $id ) ) {
			update_post_meta( $id, '_gcmn_state', 'dismissed' );
			$msg = 'Dismissed. Nothing was sent.';
		}
	}
	wp_safe_redirect( add_query_arg( array( 'page' => 'gcmn-owner-emails', 'gcmn_msg' => rawurlencode( $msg ) ), admin_url( 'admin.php' ) ) );
	exit;
} );
