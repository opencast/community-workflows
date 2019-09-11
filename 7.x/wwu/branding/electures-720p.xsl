<?xml version="1.0" encoding="UTF-8" standalone="no"?>

<xsl:stylesheet
  version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:date="http://exslt.org/dates-and-times"
  xmlns:opencast="xalan://org.opencastproject.coverimage.impl.xsl"
  exclude-result-prefixes="date opencast"
  extension-element-prefixes="date opencast">

  <xsl:param name="width"/>
  <xsl:param name="height"/>
  <xsl:param name="posterimage"/>
  <xsl:param name="ChunkSize" select="45"/>
  <xsl:param name="pChunkSize" select="40"/>

  <xsl:variable name="rawtitle">
    <xsl:value-of select="metadata/title"/>
  </xsl:variable>

  <xsl:variable name="calc">
    <xsl:value-of select="$pChunkSize + string-length(substring-before(substring($rawtitle, $pChunkSize),' '))"/>
  </xsl:variable>

  <xsl:param name="line1">
    <xsl:value-of select="substring($rawtitle,0,$calc)"/>
  </xsl:param>

  <xsl:param name="line2">
    <xsl:value-of select="substring($rawtitle,$calc)"/>
  </xsl:param>

  <xsl:variable name="title1">
    <xsl:choose>
      <xsl:when test="string-length($rawtitle) > $ChunkSize">
        <xsl:value-of select="$line1"/>
      </xsl:when>

      <xsl:otherwise>
        <xsl:value-of select="$rawtitle"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>

  <xsl:variable name="title2">
    <xsl:value-of select="$line2"/>
  </xsl:variable>

  <xsl:template match="/">
    <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1">
      <xsl:attribute name="width">
        <xsl:value-of select="$width"/>
      </xsl:attribute>

      <xsl:attribute name="height">
        <xsl:value-of select="$height"/>
      </xsl:attribute>

      <style type="text/css">
        <![CDATA[
        @font-face {
          font-family: Meta;
          src: url('/opencast/etc/branding/Meta_Regular.ttf') format('truetype');
        }
        @font-face {
          font-family: Meta;
          src: url('/opencast/etc/branding/Meta_Bold.ttf') format('truetype');
          font-weight: bold;
        }
        @font-face {
          font-family: Meta;
          src: url('/opencast/etc/branding/Meta_Italic.ttf') format('truetype');
          font-style: italic;
        }
        svg {
          font-size: 30pt;
          font-family: Meta;
        }
        .maintitle {
          font-weight: bolder;
          font-size: 1.4em;
          font-family: Meta;
        }
        .titles tspan {
          text-anchor: middle;
          font-family: Meta;
        }
        .presentationdate,
        .presenter {
          font-size: 1.2em;
          font-family: Meta;
        }
        .presenter {
          font-style: italic;
          font-family: Meta;
        }
        .license {
          font-size: 0.4em;
          font-family: Meta;
        }
        ]]>
      </style>

      <!-- Layer 1: Default Background -->
      <rect x="0" y="0" width="100%" height="100%" style="fill:white"/>

      <!-- Layer 2: Client Background (Poster Image) -->
      <xsl:if test="$posterimage">
        <image>
          <xsl:attribute name="xlink:href">
            <xsl:value-of select="$posterimage"/>
          </xsl:attribute>

          <xsl:attribute name="width">
            <xsl:value-of select="$width"/>
          </xsl:attribute>

          <xsl:attribute name="height">
            <xsl:value-of select="$height"/>
          </xsl:attribute>
        </image>
      </xsl:if>

      <!-- Layer 3: Metadata -->
      <text class="titles" x="50%">
        <tspan class="maintitle" y="40%">
          <xsl:value-of select="$title1"/>
        </tspan>

        <xsl:if test="string-length($rawtitle) > $ChunkSize">
          <tspan class="maintitle" dy="12%" x="50%">
            <xsl:value-of select="$title2"/>
          </tspan>
        </xsl:if>

        <tspan class="presenter" dy="12%" x="50%">
          <xsl:value-of select="metadata/creators"/>
        </tspan>

        <tspan class="presentationdate" dy="12%" x="50%">
          <xsl:value-of select="date:format-date(metadata/date, 'dd.MM.YYYY')"/>
        </tspan>

        <tspan class="license" dy="12%" x="50%">
          <xsl:value-of select="metadata/license"/>
        </tspan>
      </text>
    </svg>
  </xsl:template>
</xsl:stylesheet>
