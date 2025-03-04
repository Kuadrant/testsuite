<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:template match="node()|@*">
        <!-- this copies all objects that do not match any other template -->
        <xsl:copy>
            <xsl:apply-templates select="node()|@*"/>
        </xsl:copy>
    </xsl:template>

    <!-- Add full testsuite path to each testcase name -->
    <xsl:template match="testcase">
        <xsl:copy>
            <!-- Copy all attributes except name -->
            <xsl:apply-templates select="@*[not(name() = 'name')]"/>
            <!-- Modify the name attribute -->
            <xsl:attribute name="name">
                <xsl:value-of select="concat(@classname, '.', @name)"/>
            </xsl:attribute>
            <!-- Copy child nodes -->
            <xsl:apply-templates/>
        </xsl:copy>
    </xsl:template>

</xsl:stylesheet>
