<?php defined( 'ABSPATH' ) || exit; ?><!doctype html>
<html <?php language_attributes(); ?> class="no-js">
<head>
<meta charset="<?php bloginfo( 'charset' ); ?>">
<meta name="viewport" content="width=device-width, initial-scale=1">
<?php wp_head(); ?>
</head>
<body <?php body_class(); ?>>
<?php wp_body_open(); ?>
<a class="skip" href="#main">Skip to content</a>

<?php $gcmn_part = function_exists( 'gcmn_render_part' ) ? gcmn_render_part( 'header' ) : ''; ?>
<?php if ( $gcmn_part ) : ?>
<header class="top top-part"><?php echo $gcmn_part; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- Elementor output ?></header>
<?php else : ?>
<?php $gcmn_nav = gcmn_t_menu_items( 'primary' ); ?>
<header class="top">
	<div class="top-in">
		<a class="logo" href="<?php echo esc_url( home_url( '/' ) ); ?>" aria-label="<?php echo esc_attr( get_bloginfo( 'name' ) ); ?>: home">
			<img src="<?php echo esc_url( gcmn_theme_logo_url() ); ?>" alt="<?php echo esc_attr( get_bloginfo( 'name' ) ); ?>" width="130" height="54">
		</a>
		<nav class="nav" aria-label="Main">
			<ul class="nav-list">
				<?php foreach ( $gcmn_nav as $item ) : ?>
					<li class="nav-item<?php echo $item['children'] ? ' has-sub' : ''; ?><?php echo $item['class'] ? ' ' . esc_attr( $item['class'] ) : ''; ?>">
						<a href="<?php echo esc_url( $item['url'] ); ?>" <?php echo $item['current'] ? 'aria-current="page"' : ''; ?>><?php echo esc_html( $item['title'] ); ?></a>
						<?php if ( $item['children'] ) : ?>
						<ul class="sub">
							<?php foreach ( $item['children'] as $c ) : ?><li><a href="<?php echo esc_url( $c['url'] ); ?>"><?php echo esc_html( $c['title'] ); ?></a></li><?php endforeach; ?>
						</ul>
						<?php endif; ?>
					</li>
				<?php endforeach; ?>
			</ul>
		</nav>
		<button class="menu-btn" type="button" aria-expanded="false" aria-controls="menu-sheet">
			<span class="menu-label">Menu</span>
			<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M4 8h16M4 16h10"/></svg>
		</button>
	</div>
</header>

<div class="sheet" id="menu-sheet" role="dialog" aria-modal="true" aria-label="Menu" hidden>
	<div class="wrap sheet-in">
		<div class="sheet-top">
			<img src="<?php echo esc_url( gcmn_theme_logo_url( 'light' ) ); ?>" alt="<?php echo esc_attr( get_bloginfo( 'name' ) ); ?>" width="150" height="64">
			<button class="sheet-x" type="button" aria-label="Close menu">
				<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>
			</button>
		</div>
		<nav aria-label="Menu">
			<ul class="sheet-nav">
				<?php foreach ( $gcmn_nav as $i => $item ) : ?>
					<li style="--i:<?php echo (int) $i; ?>">
						<a href="<?php echo esc_url( $item['url'] ); ?>" <?php echo $item['current'] ? 'aria-current="page"' : ''; ?>><?php echo esc_html( $item['title'] ); ?></a>
						<?php if ( $item['children'] ) : ?>
						<ul class="sheet-sub"><?php foreach ( $item['children'] as $c ) : ?><li><a href="<?php echo esc_url( $c['url'] ); ?>"><?php echo esc_html( $c['title'] ); ?></a></li><?php endforeach; ?></ul>
						<?php endif; ?>
					</li>
				<?php endforeach; ?>
			</ul>
		</nav>
	</div>
</div>

<?php endif; ?>

<main id="main" tabindex="-1">
