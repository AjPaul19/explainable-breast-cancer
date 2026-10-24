<?php
defined( 'ABSPATH' ) || exit;
$name    = get_bloginfo( 'name' );
$email   = gcmn_t_opt( 'email' );
$phone   = gcmn_t_opt( 'phone' );
$address = gcmn_t_opt( 'address' );
$hours   = gcmn_t_opt( 'hours' );
$tagline = gcmn_t_opt( 'tagline' );
$social  = array();
foreach ( array( 'facebook' => 'Facebook', 'instagram' => 'Instagram', 'x' => 'X', 'youtube' => 'YouTube', 'linkedin' => 'LinkedIn' ) as $k => $label ) {
	if ( gcmn_t_opt( $k ) ) {
		$social[ $label ] = gcmn_t_opt( $k );
	}
}
$footer_items = gcmn_t_menu_items( has_nav_menu( 'footer' ) ? 'footer' : 'primary' );
?>
</main>

<?php $gcmn_foot = function_exists( 'gcmn_render_part' ) ? gcmn_render_part( 'footer' ) : ''; ?>
<?php if ( $gcmn_foot ) : ?>
<footer class="foot foot-part"><?php echo $gcmn_foot; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- Elementor output ?></footer>
<?php else : ?>
<footer class="foot">
	<div class="wrap">
		<div class="foot-grid">
			<div>
				<img src="<?php echo esc_url( gcmn_theme_logo_url( 'light' ) ); ?>" alt="<?php echo esc_attr( $name ); ?>" width="170" height="72">
				<?php if ( $tagline ) : ?><p class="foot-tag"><?php echo esc_html( $tagline ); ?></p><?php endif; ?>
			</div>
			<?php if ( $footer_items ) : ?>
			<nav aria-label="Footer">
				<h2 class="foot-h">Explore</h2>
				<ul>
					<?php foreach ( $footer_items as $item ) : ?>
						<li><a href="<?php echo esc_url( $item['url'] ); ?>"><?php echo esc_html( $item['title'] ); ?></a></li>
					<?php endforeach; ?>
				</ul>
			</nav>
			<?php endif; ?>
			<?php if ( $email || $phone || $address || $hours ) : ?>
			<div>
				<h2 class="foot-h">Reach us</h2>
				<ul>
					<?php if ( $email ) : ?><li><a href="mailto:<?php echo esc_attr( $email ); ?>"><?php echo esc_html( $email ); ?></a></li><?php endif; ?>
					<?php if ( $phone ) : ?><li><a href="tel:<?php echo esc_attr( preg_replace( '/[^\d+]/', '', $phone ) ); ?>"><?php echo esc_html( $phone ); ?></a></li><?php endif; ?>
					<?php if ( $address ) : ?><li class="foot-addr"><?php echo nl2br( esc_html( $address ) ); ?></li><?php endif; ?>
					<?php if ( $hours ) : ?><li><?php echo esc_html( $hours ); ?></li><?php endif; ?>
				</ul>
			</div>
			<?php endif; ?>
			<?php if ( $social ) : ?>
			<div>
				<h2 class="foot-h">Follow</h2>
				<ul>
					<?php foreach ( $social as $label => $url ) : ?>
						<li><a href="<?php echo esc_url( $url ); ?>" rel="noopener"><?php echo esc_html( $label ); ?></a></li>
					<?php endforeach; ?>
				</ul>
			</div>
			<?php endif; ?>
		</div>
		<p class="foot-fine">&copy; <?php echo esc_html( gmdate( 'Y' ) ); ?> <?php echo esc_html( $name ); ?></p>
	</div>
</footer>
<?php endif; ?>
<?php wp_footer(); ?>
</body>
</html>
